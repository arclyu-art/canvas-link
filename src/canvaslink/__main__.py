import argparse
import json
import os
import sys
from . import __version__
from .rate_limit import RateLimiter
from .core import load_config, Canvas, data_dir, save_config, logout, serve, http_call, DEFAULT_PORT


def mcp_config():
    if getattr(sys, "frozen", False):
        command, args = sys.executable, ["mcp"]
    else:
        command, args = sys.executable, ["-m", "canvaslink", "mcp"]
    return {"mcpServers": {"canvas-link": {"command": command, "args": args}}}


def main():
    parser = argparse.ArgumentParser(description="CanvasLink: your own Canvas session, local tools, no shared accounts.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui")
    setup = sub.add_parser("setup")
    setup.add_argument("origin")
    setup.add_argument("--login-path", default="/login")
    setup.add_argument("--browser", choices=["auto", "chrome", "msedge"], default="auto")
    setup.add_argument("--compat", action="store_true")
    setup.add_argument("--allow-writes", action="store_true")
    sub.add_parser("login")
    sub.add_parser("logout")
    sub.add_parser("status")
    limits = sub.add_parser("limits", help="View or adjust local request limits; no Canvas request")
    limits.add_argument("--interval", type=int)
    limits.add_argument("--hourly", type=int)
    limits.add_argument("--daily", type=int)
    get = sub.add_parser("get"); get.add_argument("path")
    listing = sub.add_parser("list"); listing.add_argument("path")
    request = sub.add_parser("request"); request.add_argument("file", help="Local JSON request file")
    server = sub.add_parser("serve"); server.add_argument("--port", type=int, default=DEFAULT_PORT)
    health = sub.add_parser("health"); health.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("mcp")
    sub.add_parser("mcp-config")
    doctor=sub.add_parser("doctor")
    doctor.add_argument("--browser-check",action="store_true")
    args = parser.parse_args()
    if args.command is None and getattr(sys, "frozen", False) and os.name == "nt":
        # Double-click starts a window without keeping a console behind it.
        import subprocess
        subprocess.Popen([sys.executable, "gui"], creationflags=subprocess.CREATE_NO_WINDOW)
        return
    if args.command in (None, "gui"):
        from .gui import run
        return run()
    if args.command == "mcp":
        from .mcp_server import run
        return run()
    try:
        if args.command == "setup":
            save_config(args.origin, args.login_path, args.browser, args.compat, args.allow_writes)
            result = {"configured": True}
        elif args.command == "login":
            from .login import login
            result = login(lambda message: print(message, file=sys.stderr, flush=True))
        elif args.command == "logout":
            logout(); result = {"logged_out_locally": True}
        elif args.command == "limits":
            result = RateLimiter(load_config()["origin"], data_dir()/"request-limits").configure(args.interval, args.hourly, args.daily)
        elif args.command == "status": result = Canvas().status()
        elif args.command == "get": result = Canvas().request({"path": args.path})
        elif args.command == "list": result = Canvas().list_all(args.path)
        elif args.command == "request":
            with open(args.file, encoding="utf-8-sig") as f: result = Canvas().request(json.load(f))
        elif args.command == "health": result = http_call(port=args.port)
        elif args.command == "serve": return serve(args.port)
        elif args.command == "mcp-config": result = mcp_config()
        elif args.command == "doctor":
            from .doctor import diagnose
            result=diagnose(args.browser_check)
        else: raise ValueError("Unknown command.")
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
