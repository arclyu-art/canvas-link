"""Conservative, persistent per-user/per-origin budget. Windows only; no credentials."""
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import msvcrt
import os
import secrets
from pathlib import Path
import threading
import time

MIN_INTERVAL = 5
HOURLY_LIMIT = 120
DAILY_LIMIT = 400
_thread_lock = threading.Lock()


class RateLimited(RuntimeError):
    def __init__(self, seconds):
        self.retry_after = max(1, math.ceil(seconds))
        super().__init__("RATE_LIMITED: no Canvas request sent; retry after %s seconds." % self.retry_after)


class RateLimiter:
    def __init__(self, origin, root=None):
        self.root = Path(root) if root is not None else Path(os.environ.get(
            "LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "CanvasLink" / "request-limits"
        self.path = self.root / (hashlib.sha256(origin.lower().rstrip("/").encode()).hexdigest() + ".json")
        self.handle = None
        self.locked = False

    def policy(self):
        path = self.path.with_suffix(".policy.json")
        policy = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "interval": MIN_INTERVAL, "hourly": HOURLY_LIMIT, "daily": DAILY_LIMIT}
        self.validate_policy(policy)
        return policy

    @staticmethod
    def validate_policy(policy):
        if not isinstance(policy, dict) or set(policy) != {"interval", "hourly", "daily"}:
            raise ValueError("Invalid request-limit settings.")
        for name, low, high in (("interval", 3, 60), ("hourly", 10, 300), ("daily", 10, 1000)):
            value = policy[name]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError("%s must be an integer in %s..%s." % (name, low, high))
        if policy["hourly"] > policy["daily"]:
            raise ValueError("hourly cannot exceed daily.")

    def configure(self, interval=None, hourly=None, daily=None):
        policy = self.policy()
        updates = {name: value for name, value in (("interval", interval), ("hourly", hourly), ("daily", daily)) if value is not None}
        if updates:
            policy.update(updates); self.validate_policy(policy)
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.path.with_suffix(".policy.json")
            temp = self.root / (path.name + "." + secrets.token_hex(6) + ".tmp")
            try:
                temp.write_text(json.dumps(policy), encoding="utf-8"); os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
        return policy

    def __enter__(self):
        if not _thread_lock.acquire(blocking=False):
            raise RateLimited(MIN_INTERVAL)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.handle = open(self.path.with_suffix(".lock"), "a+b")
            if self.handle.seek(0, 2) == 0:
                self.handle.write(b"0"); self.handle.flush()
            self.handle.seek(0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RateLimited(MIN_INTERVAL) from None
            self.locked = True
            self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            policy = self.policy()
            interval, hourly, daily = policy["interval"], policy["hourly"], policy["daily"]
            now = time.time()
            # Invalid state fails closed; a clock rollback cannot reset the budget.
            requests = self.state.get("requests", [])
            if (not isinstance(requests, list) or any(not isinstance(t, (int, float)) or
                    not math.isfinite(t) or t < 0 for t in requests)):
                raise ValueError("Invalid rate-limit state; no request sent.")
            requests = sorted(t for t in requests if t > now - 86400)
            for field in ("blocked_until", "strikes"):
                value = self.state.get(field, 0)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("Invalid rate-limit state; no request sent.")
            blocked = max(self.state.get("blocked_until", 0), requests[-1] if requests else 0)
            if blocked > now:
                raise RateLimited(blocked - now)
            hour = [t for t in requests if t > now - 3600]
            if len(requests) >= daily:
                raise RateLimited(requests[-daily] + 86400 - now)
            if len(hour) >= hourly:
                raise RateLimited(hour[-hourly] + 3600 - now)
            wait = max(0, requests[-1] + interval - now) if requests else 0
            if wait:
                time.sleep(wait)
            if requests and time.time() < requests[-1] + interval:
                raise RateLimited(requests[-1] + interval - time.time())
            self.state["requests"] = requests + [time.time()]
            self._save()  # Count attempts before network I/O, including failures.
            return self
        except BaseException:
            self._release()
            raise

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state), encoding="utf-8")
        os.replace(temporary, self.path)

    def observe(self, status, headers):
        now = time.time()
        if status in (429, 503):
            strikes = min(self.state.get("strikes", 0) + 1, 6)
            delay = min(86400, (1800 if status == 429 else 300) * 2 ** (strikes - 1))
            retry = headers.get("Retry-After") or headers.get("retry-after")
            if retry:
                try:
                    seconds = float(retry)
                    if math.isfinite(seconds): delay = max(delay, seconds)
                except (ValueError, TypeError):
                    try:
                        delay = max(delay, parsedate_to_datetime(retry).timestamp() - now)
                    except (ValueError, TypeError, OverflowError):
                        pass
            self.state.update(strikes=strikes, blocked_until=max(self.state.get("blocked_until", 0), now + delay))
        elif 200 <= status < 300:
            self.state["strikes"] = 0
        self._save()

    def _release(self):
        try:
            if self.handle:
                if self.locked:
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                self.handle.close()
        finally:
            self.handle = None
            self.locked = False
            _thread_lock.release()

    def __exit__(self, kind, value, traceback):
        try:
            if kind is not None:
                self.state["blocked_until"] = max(self.state.get("blocked_until", 0), time.time() + 60)
                self._save()
        finally:
            self._release()
