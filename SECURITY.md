# Security model and reporting

CanvasLink is a local, user-owned Canvas client. The account's school permissions remain authoritative. It neither generates a personal Canvas API token nor guarantees access when a school blocks session/API access.

- HTTPS only; one configured host; no arbitrary destination URL accepted by AI tools.
- No external redirect following or external-host pagination.
- Default read-only. Writes also require `allow_write=true`, a local settings opt-in and an interactive Windows confirmation displaying the method, path and JSON payload.
- Optional HTTP binds only to IPv4 loopback, checks exact Host and bearer authentication, rejects browser Origin/Fetch Metadata requests, and emits no CORS headers.
- Logs do not contain request bodies or access URLs. MCP tool results themselves can contain private course information and should not be published.
- Local HTTP 200 does not imply upstream Canvas success. Failed or partial list reads are not returned as successful empty lists.
- Browser/HTML course content is untrusted data. It cannot grant permission to submit, delete or send anything.
- Mutations are never automatically retried after a network failure.

Report reproducible issues privately to the repository owner through their GitHub security-advisory contact if enabled. Include a synthetic reproduction, never live cookies, session files, private assignment text or student identifiers.

The Windows binary is unsigned in this initial release. Build from source or verify release checksums if required by your environment. No school or Canvas vendor endorsement is implied.

This release has automated local boundary, encryption and MCP protocol tests. It has not been independently security-audited or verified at every Canvas institution.

## Conservative request limits

All application API requests, pagination and login identity checks share a persisted per-Windows-user, per-Canvas-origin budget: one in-flight request, by default at least 5 seconds between starts, at most 120 attempts per rolling hour and 400 per rolling day. State lives under `%LOCALAPPDATA%/CanvasLink/request-limits`; isolated test data directories use their own state. Requests from the legacy bridge share this default budget too. Restarting or changing login does not reset it. Do not delete limit files to bypass a cooldown.

HTTP 429 triggers at least 30 minutes of cooldown, repeated throttling increases it, and a longer `Retry-After` (seconds or HTTP date) is respected. HTTP 503 starts at 5 minutes; 401 invalidates the saved Canvas session and requires a fresh login, without adding a cooldown; 403 is a permission denial, not throttling; transport failures pause for 60 seconds. No request is automatically retried. Budget/cooldown refusal returns `RATE_LIMITED` with a wait time; the optional local HTTP interface returns 429 with `local_rate_limit=true`. This is a local refusal, not an upstream Canvas response or an empty result. Long cooldowns do not sleep inside the process. Failed/corrupt budget state prevents requests.

A nine-request scan now needs at least about 40 seconds plus network time. These limits cover requests made by the application, not browser page assets or unrelated clients. They reduce traffic; they do not constitute school/vendor approval for session or MCP access.

### Adjustable limits

Default: 5 seconds between request starts, 120/hour, 400/day. Settings are shared per Canvas origin, loaded on every request, and never clear request history or server cooldowns. One request remains in flight; 429/503 cooldowns cannot be disabled.

Windows CLI: `CanvasLink.exe limits` shows settings; `CanvasLink.exe limits --interval 5 --hourly 120 --daily 400` saves them. Bounds: interval 3..60 seconds, hourly 10..300, daily 10..1000; hourly must not exceed daily. No network request is made. The legacy CLI supports the same flags: `python bridge.py limits --interval 5 --hourly 120 --daily 400`.

For slow custom intervals or long paginated reads, the AI client/local HTTP caller may need a longer request timeout. The recommended 5-second default avoids a single pacing wait near the usual 60-second client timeout.
