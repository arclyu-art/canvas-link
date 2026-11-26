# CanvasLink

[简体中文](README.md) | **English**

**Connect AI on your computer to your own Canvas account.** A local Windows tool supporting school web login, SSO/MFA, local MCP, and an optional loopback HTTP interface.

No shared account, preconfigured school or course, or developer-hosted backend. Each user configures and signs in on their own computer.

Before using it, confirm that your school and service provider allow this integration. The [Instructure API policy](https://www.instructure.com/policies/canvas-api-policy) restricts unapproved MCP and other integrations; this project has no evidence of such approval. If your school disables token generation, browser session cookies do not constitute an alternative authorization. Rate limiting and local encryption do not remove this policy risk.

**[Download for Windows](https://github.com/arclyu-art/canvas-link/releases/latest/download/CanvasLink-windows-x64.zip)** · [All releases](https://github.com/arclyu-art/canvas-link/releases)

## Windows setup

1. Download `CanvasLink-windows-x64.zip` from **Releases** and extract the entire archive.
2. Open `CanvasLink.exe`. Keep the adjacent `_internal` folder; do not copy the EXE alone.
3. Enter your school's Canvas address, such as `https://school.instructure.com`, and save the settings.
4. Select the Canvas login button and complete school login and MFA in the separate Edge/Chrome window. The window closes after Canvas identity verification succeeds.
5. Check the connection to confirm that upstream authentication is valid.
6. Copy the MCP configuration and register it with an AI client that supports **local stdio MCP**.

Requires Windows 10/11 x64 and installed Microsoft Edge or Google Chrome. No separate Python installation is required; the package does not bundle a full browser. The initial release is unsigned.

Signing in through your everyday browser does not sign in the tool's separate browser context. Sign in again when the session expires. The tool does not bypass school MFA.

## How it works

CanvasLink is primarily a Canvas API client that reuses the user's authenticated session: it requests JSON from `/api/v1` and also supports some course HTML and file paths. It is not primarily a traditional HTML-parsing crawler, but it remains third-party automated access. Using an API, session cookies, or low request rates does not itself establish school or vendor approval.

## What AI can do

- Read courses, assignment instructions, deadlines, rubrics, and your submission status.
- Read course pages, modules, file listings, and announcements.
- Retrieve complete lists through validated same-origin pagination.
- Summarize material and help with study or planning. Scheduled reminders depend on the AI client's scheduling capability; this tool does not create scheduled tasks automatically.
- Default to read-only access. Optional changes require individual local approval.

An arbitrary web-based AI cannot necessarily access your computer. This tool supplies local MCP; the client must be able to launch local MCP subprocesses. It includes no model, AI account, or model API key.

Example MCP configuration; the setup window generates the actual executable path:

```json
{
  "mcpServers": {
    "canvas-link": {
      "command": "C:\\Apps\\CanvasLink\\CanvasLink.exe",
      "args": ["mcp"]
    }
  }
}
```

The configuration contains no Canvas password, cookie, or local HTTP key. The MCP subprocess reads the encrypted session under the user's Windows identity. MCP stdout contains protocol data only.

## Local data and privacy

Settings and DPAPI-encrypted sessions are stored in `%LOCALAPPDATA%\CanvasLink`, outside the extracted application directory. Passwords are not saved; everyday browser profiles are not read; school SSO storage is not exported. Clear the saved login to remove the local Canvas session.

Requested course content is passed to the AI client and potentially its model provider. See [PRIVACY.md](PRIVACY.md).

## Advanced settings and limitations

- The default login path is `/login`; use `/login/saml` if your school requires SAML.
- Connection compatibility mode may help with login connection resets. It does not disable TLS verification.
- School policies, browser automation restrictions, or API permissions may prevent access. Not every Canvas feature is available through equivalent API functionality.
- Gradescope, publisher platforms, and external LTI tools require separate authorization and integration.
- External signed file links are not automatically followed with Canvas cookies.
- Writes support JSON/form API requests, not multi-stage large-file uploads. Each local confirmation preview is limited to 4,000 characters.
- Responses are limited to 16 MiB; lists to 100 pages/20,000 entries. Narrow the query if a limit is reached.
- Windows only in this initial release; macOS/Linux have not been verified. The MCP SDK is pinned to its 1.x maintenance line to avoid automatic major-version protocol changes.

## Command line

```powershell
.\CanvasLink.exe setup https://school.instructure.com
.\CanvasLink.exe login
.\CanvasLink.exe status
.\CanvasLink.exe list '/api/v1/courses?enrollment_state=active&per_page=100'
.\CanvasLink.exe get '/api/v1/users/self/profile'
.\CanvasLink.exe logout
.\CanvasLink.exe mcp-config
.\CanvasLink.exe doctor --browser-check
```

Optional legacy local HTTP interface: `CanvasLink.exe serve --port 8766`. Python callers under the same Windows identity can use `canvaslink.core.http_call()`. This is an authenticated local interface, not a public web endpoint. MCP does not require it to be running.

## Development and running from source

Install Python 3.11+ and run these commands in the Windows project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m canvaslink
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build_windows.py
.\.venv\Scripts\python.exe release.py
```

Do not copy anyone's session for testing. Tests create synthetic data in a temporary `CANVASLINK_DATA_DIR`; they do not read the default user directory or access real Canvas accounts.

## Publishing to GitHub

This directory contains the standalone repository. Publish its source files, not the surrounding personal workspace. `release.py` uses an explicit file allowlist to create clean source archives.

The project includes an MIT license, privacy and security documentation, tests, and GitHub Actions. Actions tests and builds on Windows. Pushing a `v*` tag publishes a GitHub release with a Windows ZIP and SHA256 checksums.

```powershell
git init
git add .
git commit -m "Initial CanvasLink release"
# Configure the remote using your new GitHub repository page, then push.
# Replace vX.Y.Z with an unused version before publishing:
# git tag vX.Y.Z; git push origin vX.Y.Z
```

Check that no personal config, session, or snapshot is included before publishing. Deleting a previously committed credential is insufficient: revoke it and clean the Git history.

## Technical references

- [Official MCP Python SDK 1.x](https://py.sdk.modelcontextprotocol.io/v1/)
- [Connecting local MCP servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Playwright browsers and Chrome/Edge channels](https://playwright.dev/python/docs/browsers)
- [Playwright and PyInstaller](https://playwright.dev/python/docs/library#pyinstaller)
- [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Canvas API pagination](https://developerdocs.instructure.com/services/canvas/basics/file.pagination)

## Request frequency and adjustable limits

Application API calls, pagination, and login identity checks share a persisted per-Windows-user, per-Canvas-origin budget: one in-flight request per origin, a default minimum **5-second** start interval, **120 attempts per rolling hour**, and **400 per rolling day**. State is stored in `%LOCALAPPDATA%/CanvasLink/request-limits`; tests use isolated temporary directories. The legacy bridge shares the default directory's budget. Restarting or signing in again does not reset it. Do not delete limit files to bypass a cooldown.

- **429:** at least 30 minutes of cooldown, increasing after repeated throttling; a longer server `Retry-After` in seconds or HTTP-date format is respected.
- **503:** cooldown starts at 5 minutes.
- **401:** invalidates the saved Canvas session and requires a fresh login, without adding a cooldown.
- **403:** permission denial, not throttling.
- **Transport errors:** pause for 60 seconds; requests are not automatically retried.

Budget or cooldown refusal returns `RATE_LIMITED` with a wait time. The optional local HTTP interface returns 429 with `local_rate_limit=true`. This is a local refusal, not an upstream Canvas response or a successful empty list. Long cooldowns do not keep the process sleeping; corrupt limit state prevents requests.

### View and adjust settings

```powershell
.\CanvasLink.exe limits
.\CanvasLink.exe limits --interval 5 --hourly 120 --daily 400
```

Allowed ranges: **3–60 seconds** between starts, **10–300 attempts/hour**, and **10–1000 attempts/day**. The hourly budget cannot exceed the daily budget. Settings are shared per Canvas origin and reloaded for every request. Adjusting them never clears request history or server cooldowns, or disables serialization and 429/503 cooldowns. Viewing or changing settings sends no Canvas request.

The legacy CLI supports the same flags: `python bridge.py limits --interval 5 --hourly 120 --daily 400`.

At the default interval, nine request starts span at least about 40 seconds; allow for network time as well. These limits cover application requests, not browser page assets or other clients. Slow custom intervals or long paginated reads may require a longer AI-client or local-HTTP timeout. Start with the recommended 5-second default.
