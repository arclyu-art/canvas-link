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
