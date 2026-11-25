"""Interactive login only; never read an existing browser profile or account password."""
import json
import time
import urllib.parse
from .core import load_config, data_dir, load_secret, save_secret


def login(notify=lambda message: None):
    from playwright.sync_api import sync_playwright, Error as BrowserError
    config = load_config()
    origin = config["origin"]
    host = urllib.parse.urlsplit(origin).hostname
    with sync_playwright() as p:
        choices = [config["browser"]] if config["browser"] != "auto" else ["msedge", "chrome"]
        browser = None
        for channel in choices:
            try:
                browser = p.chromium.launch(channel=channel, headless=False,
                    args=["--disable-http2", "--disable-quic"] if config.get("compat") else [])
                break
            except BrowserError:
                pass
        if browser is None:
            raise RuntimeError("No supported browser could open. Install/update Microsoft Edge or Google Chrome, then retry.")
        context = browser.new_context()
        if (data_dir() / "session.dpapi").exists():
            stored = load_secret("session")
            if stored.get("origin") == origin:
                context.add_cookies(stored["cookies"])
        page = context.new_page()
        try:
            page.goto(origin + config["login_path"], wait_until="domcontentloaded", timeout=60000)
        except BrowserError:
            notify("Navigation interrupted. You can reload or navigate to Canvas in this login window.")
        notify("Complete your own school login and MFA in the browser. No password is read or saved by CanvasLink.")
        deadline = time.monotonic() + 1800
        try:
            while time.monotonic() < deadline:
                if page.is_closed():
                    raise RuntimeError("Login window closed before Canvas identity was verified.")
                if urllib.parse.urlsplit(page.url).hostname == host:
                    try:
                        response = context.request.get(origin + "/api/v1/users/self/profile", timeout=10000, max_redirects=0)
                        if response.status == 200 and "json" in response.headers.get("content-type", ""):
                            profile = response.json()
                            if isinstance(profile, dict) and profile.get("id"):
                                # Save only Canvas cookies. No CAS/SSO/Duo storage state is exported.
                                save_secret("session", {"origin": origin, "cookies": context.cookies(origin)})
                                notify("Canvas identity verified. The encrypted session is stored only in this Windows account.")
                                return {"authenticated": True}
                    except BrowserError:
                        pass
                    except json.JSONDecodeError:
                        pass
                page.wait_for_timeout(2000)
            raise RuntimeError("Login timed out after 30 minutes. No verified session was saved.")
        finally:
            browser.close()
