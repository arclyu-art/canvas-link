"""Local diagnostics without reading course data or account identities."""
import os
from importlib.metadata import version


def diagnose(check_browser=False):
    result={"windows":os.name=="nt","playwright":version("playwright"),"mcp":version("mcp")}
    if check_browser:
        from playwright.sync_api import sync_playwright, Error
        result["browser_ok"]=False
        with sync_playwright() as p:
            for channel in ("msedge","chrome"):
                try:
                    browser=p.chromium.launch(channel=channel,headless=True)
                    page=browser.new_page();page.goto("about:blank")
                    assert page.evaluate("1 + 1")==2
                    browser.close();result.update(browser_ok=True,browser=channel)
                    break
                except Error:
                    continue
    return result
