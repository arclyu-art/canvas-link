"""Standard-library Canvas client, Windows encrypted storage, optional loopback HTTP."""
import ctypes
from ctypes import wintypes
import base64
import http.client
import http.cookiejar
from http.server import HTTPServer, BaseHTTPRequestHandler
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
import urllib.parse
import urllib.request

MAX_BODY = 2 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
DEFAULT_PORT = 8766


class LoginRequired(RuntimeError):
    pass


def data_dir():
    if os.name != "nt":
        raise RuntimeError("This release supports Windows only.")
    if os.environ.get("CANVASLINK_DATA_DIR"):
        return Path(os.environ["CANVASLINK_DATA_DIR"]).expanduser().resolve()
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "CanvasLink"


def validate_origin(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        raise ValueError("Enter an HTTPS Canvas address, without spaces.")
    url = urllib.parse.urlsplit(value.strip())
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Canvas address must use HTTPS, with no embedded credentials.")
    if url.path not in ("", "/") or url.query or url.fragment or url.port not in (None, 443):
        raise ValueError("Use only the Canvas site origin, without a path, query or custom port.")
    host = url.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if not re.fullmatch(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        raise ValueError("Invalid Canvas hostname.")
    if "." not in host or host.endswith((".localhost", ".local")) or ".." in host:
        raise ValueError("Use a public Canvas hostname.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Use your school's Canvas hostname, not an IP address.")
    return "https://" + host


def validate_path(path):
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise ValueError("Use a Canvas-relative path starting with one /.")
    if not path.isascii():
        raise ValueError("URL-encode non-ASCII path characters.")
    current = path
    for _ in range(8):
        if "\\" in current or "#" in current or current.startswith("//") or any(ord(c) < 32 or ord(c) == 127 for c in current):
            raise ValueError("Invalid path.")
        if any(p in (".", "..") for p in current.split("?", 1)[0].split("/")):
            raise ValueError("Path traversal is not allowed.")
        decoded = urllib.parse.unquote(current)
        if decoded == current:
            return path
        current = decoded
    raise ValueError("Too many nested URL encodings.")


def load_config():
    path = data_dir() / "config.json"
    if not path.exists():
        raise RuntimeError("SETUP_REQUIRED: open CanvasLink and save your Canvas address first.")
    config = json.loads(path.read_text(encoding="utf-8"))
    config["origin"] = validate_origin(config["origin"])
    config["login_path"] = validate_path(config.get("login_path", "/login"))
    if config.get("browser", "auto") not in ("auto", "chrome", "msedge"):
        raise ValueError("Invalid browser setting.")
    return config


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / ("." + path.name + "." + secrets.token_hex(6) + ".tmp")
    try:
        with open(temporary, "xb") as f:
            f.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_config(origin, login_path="/login", browser="auto", compat=False, allow_writes=False):
    config = {"origin": validate_origin(origin), "login_path": validate_path(login_path),
              "browser": browser, "compat": bool(compat), "allow_writes": bool(allow_writes)}
    if browser not in ("auto", "chrome", "msedge"):
        raise ValueError("Choose auto, chrome or msedge.")
    path = data_dir() / "config.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("origin") != config["origin"]:
            logout()
    atomic_write(path, json.dumps(config, indent=2).encode("utf-8"))
    return config


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required; no plaintext fallback is provided.")
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, dest = Blob(len(data), buffer), Blob()
    fn = api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(dest)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(dest.data, dest.size)
    finally:
        kernel.LocalFree(dest.data)


def save_secret(name, value):
    if name not in ("session", "bridge-key"):
        raise ValueError("Unknown secret name.")
    atomic_write(data_dir() / (name + ".dpapi"), crypt(json.dumps(value).encode("utf-8")))


def load_secret(name):
    if name not in ("session", "bridge-key"):
        raise ValueError("Unknown secret name.")
    return json.loads(crypt((data_dir() / (name + ".dpapi")).read_bytes(), True))


def logout():
    (data_dir() / "session.dpapi").unlink(missing_ok=True)


def local_key():
    if not (data_dir() / "bridge-key.dpapi").exists():
        save_secret("bridge-key", secrets.token_urlsafe(32))
    return load_secret("bridge-key")


def cookie_jar(cookies):
    jar = http.cookiejar.CookieJar()
    for c in cookies:
        expiry = c.get("expires", -1)
        jar.set_cookie(http.cookiejar.Cookie(0, c["name"], c["value"], None, False, c["domain"],
            c["domain"].startswith("."), c["domain"].startswith("."), c.get("path", "/"), True,
            c.get("secure", True), int(expiry) if expiry > 0 else None, expiry <= 0,
            None, None, {"HttpOnly": c.get("httpOnly", False)}, False))
    return jar


def export_cookies(jar):
    return [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
             "secure": c.secure, "expires": c.expires or -1,
             "httpOnly": bool(c._rest.get("HttpOnly", False))} for c in jar]


def approve_write(method, path, preview):
    if os.name != "nt":
        return False
    # Fail closed outside an interactive desktop. Never auto-approve a mutation.
    text = "An AI/local client requests a Canvas change.\n\n" + method + " " + path + "\n\nPayload:\n" + preview + "\n\nOnly approve if you requested this exact change."
    return ctypes.windll.user32.MessageBoxW(None, text, "CanvasLink: approve change", 0x4 | 0x30 | 0x100 | 0x1000) == 6


class Canvas:
    def __init__(self):
        self.origin = None
        self.host = None
        self.config = None
        self.conn = None
        self.stamp = None
        self.jar = http.cookiejar.CookieJar()
        self.lock = threading.RLock()

    def close(self):
        if self.conn:
            self.conn.close()
        self.conn = None

    def reload(self):
        config = load_config()
        if self.origin != config["origin"]:
            self.close()
            self.origin = config["origin"]
            self.host = urllib.parse.urlsplit(self.origin).hostname
            self.stamp = None
        self.config = config
        path = data_dir() / "session.dpapi"
        if not path.exists():
            self.jar = http.cookiejar.CookieJar()
            self.stamp = None
            raise LoginRequired("NEEDS_LOGIN: open CanvasLink and click Login.")
        stamp = path.stat().st_mtime_ns
        if stamp != self.stamp:
            session = load_secret("session")
            if session.get("origin") != self.origin:
                raise LoginRequired("NEEDS_LOGIN: saved session belongs to another Canvas address.")
            self.jar = cookie_jar(session["cookies"])
            self.stamp = stamp

    def request(self, spec):
        with self.lock:
            return self._request(spec)

    def _request(self, spec):
        if not isinstance(spec, dict):
            raise ValueError("Request must be an object.")
        path = validate_path(spec.get("path"))
        if not path.startswith(("/api/v1/", "/courses/", "/files/")):
            raise ValueError("Use /api/v1/, /courses/ or /files/; login/logout routes are not exposed.")
        method = spec.get("method", "GET")
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise ValueError("Unsupported method.")
        if method == "GET" and ("json" in spec or "form" in spec):
            raise ValueError("GET cannot contain a body.")
        if "json" in spec and "form" in spec:
            raise ValueError("Choose json or form, not both.")
        if method != "GET" and (not path.startswith("/api/v1/") or spec.get("allow_write") is not True):
            raise ValueError("Writes require an /api/v1/ path and allow_write=true.")
        self.reload()
        if method != "GET":
            if not self.config.get("allow_writes"):
                raise PermissionError("Read-only mode. Enable writes yourself in CanvasLink settings first.")
            preview = json.dumps(spec.get("json", spec.get("form", {})), ensure_ascii=False, indent=2)
            if len(preview) + len(path) > 4000:
                raise ValueError("Mutation is too large to review in the local confirmation window.")
            if not approve_write(method, path, preview):
                raise PermissionError("The local user did not approve this change.")
        req = urllib.request.Request(self.origin + path, method=method)
        self.jar.add_cookie_header(req)
        headers = dict(req.header_items())
        headers.update({"Accept": "application/json" if path.startswith("/api/") else "*/*",
                        "Accept-Encoding": "identity", "User-Agent": "CanvasLink/0.1"})
        payload = None
        if method != "GET":
            csrf = next((c.value for c in self.jar if c.name == "_csrf_token" and
                         (self.host == c.domain.lstrip(".") or self.host.endswith("." + c.domain.lstrip(".")))), None)
            if not csrf:
                raise LoginRequired("NEEDS_LOGIN: CSRF cookie unavailable.")
            headers.update({"X-CSRF-Token": urllib.parse.unquote(csrf), "Origin": self.origin, "Referer": self.origin + "/"})
        if "json" in spec:
            payload = json.dumps(spec["json"]).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif "form" in spec:
            payload = urllib.parse.urlencode(spec["form"], doseq=True).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if payload and len(payload) > MAX_BODY:
            raise ValueError("Request body exceeds 2 MiB.")
        started = time.perf_counter()
        for attempt in range(2 if method == "GET" else 1):
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPSConnection(self.host, timeout=30)
                self.conn.request(method, path, body=payload, headers=headers)
                response = self.conn.getresponse()
                previous = export_cookies(self.jar)
                self.jar.extract_cookies(response, req)
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise ValueError("Response exceeds 16 MiB; request a smaller page.")
                break
            except (OSError, http.client.HTTPException):
                self.close()
                if method != "GET" or attempt == 1:
                    raise RuntimeError("Canvas network request failed. Do not retry a write until its outcome is checked.") from None
            except Exception:
                self.close()
                raise
        if response.will_close:
            self.close()
        if previous != export_cookies(self.jar):
            save_secret("session", {"origin": self.origin, "cookies": export_cookies(self.jar)})
            self.stamp = (data_dir() / "session.dpapi").stat().st_mtime_ns
        content_type = response.getheader("Content-Type", "")
        out = {"status": response.status, "elapsed_ms": round((time.perf_counter() - started) * 1000),
               "content_type": content_type, "headers": {name: response.getheader(name) for name in
                ("Link", "Location", "Retry-After") if response.getheader(name)}}
        if "json" in content_type:
            text = body.decode("utf-8-sig").removeprefix("while(1);")
            out["data"] = json.loads(text) if text.strip() else None
        elif "text/" in content_type or "xml" in content_type:
            out["data"] = body.decode("utf-8", errors="replace")
        else:
            out["data_base64"] = base64.b64encode(body).decode("ascii")
        if response.status in (401, 403) or (path.startswith("/api/") and "text/html" in content_type):
            out["needs_login"] = response.status == 401 or "text/html" in content_type
        if 300 <= response.status < 400:
            out["redirect_not_followed"] = True
        return out

    def status(self):
        try:
            result = self.request({"path": "/api/v1/users/self/profile"})
            verified = result["status"] == 200 and isinstance(result.get("data"), dict) and bool(result["data"].get("id"))
            return {"configured": True, "authenticated": verified, "upstream_status": result["status"],
                    "needs_login": bool(result.get("needs_login")), "read_only": not self.config.get("allow_writes", False)}
        except LoginRequired:
            return {"configured": True, "authenticated": False, "needs_login": True}
        except RuntimeError as error:
            if str(error).startswith("SETUP_REQUIRED"):
                return {"configured": False, "authenticated": False, "needs_setup": True}
            raise

    def list_all(self, path, max_pages=100):
        if not isinstance(max_pages, int) or not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be 1..100.")
        items, requests, seen = [], [], set()
        while path:
            if path in seen or len(seen) >= max_pages:
                raise RuntimeError("Pagination incomplete: no partial list is returned as complete.")
            seen.add(path)
            result = self.request({"path": path})
            requests.append({"status": result["status"], "elapsed_ms": result["elapsed_ms"]})
            if result["status"] != 200 or not isinstance(result.get("data"), list):
                return {"ok": False, "requests": requests, "failed_response": result,
                        "note": "Incomplete Canvas read. Do not interpret this as an empty list."}
            items.extend(result["data"])
            if len(items) > 20000:
                raise ValueError("List exceeds 20000 items. Narrow the query.")
            match = re.search(r'<([^>]+)>;\s*rel="next"', result.get("headers", {}).get("Link", ""))
            path = None
            if match:
                target = urllib.parse.urlsplit(match.group(1))
                if target.scheme != "https" or target.netloc.lower() != self.host:
                    raise ValueError("Cross-origin pagination rejected.")
                path = validate_path(target.path + ("?" + target.query if target.query else ""))
        return {"ok": True, "items": items, "requests": requests}


class Handler(BaseHTTPRequestHandler):
    server_version = "CanvasLink/0.1"
    def log_message(self, *_):
        pass
    def setup(self):
        super().setup()
        self.connection.settimeout(10)
    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, value in {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
                            "X-Content-Type-Options": "nosniff", "Content-Length": str(len(body))}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
    def authorized(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}" or self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site"):
            self.reply(403, {"error": "Use an authenticated local client, not a web page."})
            return False
        given = self.headers.get("Authorization", "").encode()
        if not secrets.compare_digest(given, ("Bearer " + self.server.key).encode()):
            self.reply(401, {"error": "Local bridge authentication required."})
            return False
        return True
    def do_GET(self):
        if not self.authorized(): return
        if self.path != "/health": return self.reply(404, {"error": "Unknown endpoint."})
        self.reply(200, {"ok": True, "note": "Local service only; use Canvas status to verify upstream authentication."})
    def do_POST(self):
        if not self.authorized(): return
        if self.path != "/request": return self.reply(404, {"error": "Unknown endpoint."})
        try:
            if self.headers.get("Transfer-Encoding"): raise ValueError("Chunked requests are not accepted.")
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json": raise ValueError("Use application/json.")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY: raise ValueError("Invalid body size.")
            result = self.server.canvas.request(json.loads(self.rfile.read(size)))
            self.reply(200, result)
        except LoginRequired:
            self.reply(409, {"needs_login": True, "error": "Open CanvasLink and log in."})
        except PermissionError as e:
            self.reply(403, {"error": str(e)})
        except (ValueError, TypeError):
            self.reply(400, {"error": "Invalid Canvas request."})
        except Exception:
            self.reply(502, {"error": "Upstream read failed; do not treat as empty data or retry mutations blindly."})


class ExclusiveServer(HTTPServer):
    allow_reuse_address = False
    def server_bind(self):
        if os.name == "nt": self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(port=DEFAULT_PORT):
    load_config()
    with ExclusiveServer(("127.0.0.1", port), Handler) as server:
        server.key = local_key()
        server.canvas = Canvas()
        try: server.serve_forever()
        finally: server.canvas.close()


def http_call(spec=None, port=DEFAULT_PORT):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=65)
    try:
        headers = {"Authorization": "Bearer " + local_key(), "Content-Type": "application/json"}
        conn.request("POST" if spec is not None else "GET", "/request" if spec is not None else "/health",
                     None if spec is None else json.dumps(spec), headers)
        response = conn.getresponse()
        return {"local_status": response.status, "response": json.loads(response.read())}
    finally:
        conn.close()
