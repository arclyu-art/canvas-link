import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from email.utils import formatdate
from canvaslink import rate_limit as limits


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1_800_000_000.0
        self.time = patch.object(limits.time, "time", side_effect=lambda: self.now)
        self.sleep = patch.object(limits.time, "sleep", side_effect=self.advance)
        self.time.start(); self.sleep_mock = self.sleep.start()
        self.budget().configure(interval=10, hourly=60, daily=200)
        self.addCleanup(self.time.stop); self.addCleanup(self.sleep.stop)

    def advance(self, seconds):
        self.now += seconds

    def budget(self):
        return limits.RateLimiter("https://canvas.example.edu", self.temp.name)

    def test_adjustment_is_shared_and_does_not_clear_cooldown(self):
        with self.budget() as b: b.observe(429, {})
        self.budget().configure(interval=5, hourly=120, daily=400)
        self.assertEqual(self.budget().policy(), {"interval":5,"hourly":120,"daily":400})
        with self.assertRaises(limits.RateLimited):
            with self.budget(): pass
        self.advance(1801)
        with self.budget(): pass
        with self.budget(): pass
        self.assertEqual(self.sleep_mock.call_args.args, (5,))
        for values in ({"interval":0},{"interval":float("nan")},{"hourly":301},{"daily":1001},{"hourly":200,"daily":100}):
            with self.assertRaises(ValueError): self.budget().configure(**values)

    def test_spacing_persists_across_instances(self):
        with self.budget(): pass
        with self.budget(): pass
        self.assertEqual(self.sleep_mock.call_args.args, (10,))
        state = json.loads(self.budget().path.read_text())
        self.assertEqual(state["requests"][1] - state["requests"][0], 10)

    def test_hourly_and_daily_budgets(self):
        for _ in range(60):
            with self.budget(): pass
        with self.assertRaises(limits.RateLimited) as error:
            with self.budget(): self.fail("hour budget bypassed")
        self.assertGreater(error.exception.retry_after, 0)
        self.advance(3601)
        with self.budget(): pass
        budget = self.budget()
        budget.path.write_text(json.dumps({"requests": [self.now - 80000 + i * 400 for i in range(200)]}))
        with self.assertRaises(limits.RateLimited):
            with self.budget(): self.fail("day budget bypassed")

    def test_429_retry_after_seconds_and_date_and_escalation(self):
        with self.budget() as budget:
            budget.observe(429, {"Retry-After": "7200"})
        self.advance(1801)
        with self.assertRaises(limits.RateLimited) as error:
            with self.budget(): pass
        self.assertEqual(error.exception.retry_after, 5399)
        self.advance(5400)
        with self.budget() as budget:
            budget.observe(429, {"retry-after": formatdate(self.now + 10000, usegmt=True)})
        self.advance(3601)
        with self.assertRaises(limits.RateLimited) as error:
            with self.budget(): pass
        self.assertEqual(error.exception.retry_after, 6399)
        self.advance(6400)
        with self.budget() as budget:
            budget.observe(429, {"Retry-After": "invalid"})
        self.assertEqual(budget.state["blocked_until"] - self.now, 7200)

    def test_errors_cool_down_and_clock_rollback_fails_closed(self):
        for status, seconds in [(503, 300)]:
            with self.budget() as budget: budget.observe(status, {})
            with self.assertRaises(limits.RateLimited):
                with self.budget(): pass
            self.advance(seconds + 1)
        self.now -= 100
        with self.assertRaises(limits.RateLimited):
            with self.budget(): pass
        self.advance(101)
        with self.assertRaises(OSError):
            with self.budget(): raise OSError("simulated network error")
        with self.assertRaises(limits.RateLimited):
            with self.budget(): pass

    def test_auth_errors_do_not_create_a_cooldown(self):
        for status in (401, 403):
            with self.budget() as budget: budget.observe(status, {})
            self.assertEqual(budget.state.get("blocked_until", 0), 0)
            with self.budget(): pass

    def test_corrupt_state_fails_closed_and_releases_lock(self):
        budget = self.budget(); budget.path.parent.mkdir(parents=True, exist_ok=True)
        budget.path.write_text("not json")
        with self.assertRaises(ValueError):
            with self.budget(): pass
        budget.path.write_text("{}")
        with self.budget(): pass

    def test_processes_cannot_send_concurrently(self):
        # A real second process holds the same origin lock; no network is used.
        code = ("import importlib.util,sys; "
                "s=importlib.util.spec_from_file_location('limits',sys.argv[1]); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "b=m.RateLimiter('https://canvas.example.edu',sys.argv[2]); "
                "b.__enter__(); print('locked',flush=True); input(); b.__exit__(None,None,None)")
        p = subprocess.Popen([sys.executable, "-c", code, limits.__file__, self.temp.name],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(), "locked")
            with self.assertRaises(limits.RateLimited):
                with self.budget(): self.fail("concurrent request allowed")
            p.communicate("done\n", timeout=10)
            self.assertEqual(p.returncode, 0)
        finally:
            if p.poll() is None: p.kill(); p.communicate()


if __name__ == "__main__": unittest.main()
