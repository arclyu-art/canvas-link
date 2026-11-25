# Privacy

CanvasLink has no developer-hosted backend, analytics, registration service or telemetry.

## What is stored

On the user's Windows account, under `%LOCALAPPDATA%\CanvasLink`:

- `config.json`: the user's chosen Canvas origin, login path, browser and local permission switches.
- `session.dpapi`: verified Canvas cookies, encrypted with Windows current-user DPAPI.
- `bridge-key.dpapi`: an encrypted local HTTP key, created only if that optional interface is used.

The application directory and GitHub project do not contain these files. Moving or sharing the executable does not move an account's session. `CANVASLINK_DATA_DIR` can override this location for isolated tests; do not use a shared folder for real accounts.

School passwords are entered by the user on the school's browser page. The application does not read password fields or save passwords. It uses a new browser context; it does not read the user's everyday Chrome/Edge profile. Only Canvas-origin cookies are exported after `/api/v1/users/self/profile` verifies the login. School SSO cookies and browser storage state are not exported.

## Where data goes

- Login: the configured Canvas site and its school-selected identity provider/MFA service, through the interactive browser.
- Course requests: only the configured HTTPS Canvas host. Upstream redirects are returned, not automatically followed with cookies.
- AI integration: requested course content is returned to the user's MCP host. That host may send it to its selected model provider. Local transport does not mean model processing is offline.
- Dependencies: a source installation or a GitHub build downloads packages from its configured package index. A downloaded Windows release requires no package installation.

CanvasLink does not send data to its authors. It does not provide a shared login or a cloud proxy.

## Deleting local data

The UI's clear-login button removes the saved Canvas session. Settings remain. To remove everything, close CanvasLink and its MCP clients and remove the application-specific `%LOCALAPPDATA%\CanvasLink` directory yourself. Clearing local cookies does not revoke sessions on the school server; use the school's account/session management for that.

DPAPI protects secrets at rest for a Windows user account. Programs already running as that user can potentially decrypt them. It is not an isolation boundary against malware controlling that account.

## Publication boundary

Use the release script's explicit file allowlist. Do not zip a personal working folder, browser profile, AppData directory, virtual environment, transcript or Canvas snapshot. Git ignore rules alone do not remove secrets already committed to a Git repository.
