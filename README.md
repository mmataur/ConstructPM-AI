# ConstructPM AI â€” Phase 1 foundation

React + TypeScript + Tauri desktop source and a PostgreSQL-backed FastAPI foundation. Phase 2 scheduling has not been started.

## What is available

* Company registration for a verified signed-in identity; first administrator created atomically.
* OIDC bearer-token verification (signature, issuer, audience, expiry and verified email); isolated loopback-only demonstration identities, disabled by default.
* Company discovery, administrator/member roles, single-use expiring invitations, member activation/deactivation and last-administrator protection.
* Projects, eight project roles, explicit project assignment, optimistic concurrency and archiving.
* Validated construction calendar shifts, nonworking days/date exceptions and immutable historical versions.
* Append-only audit history and transactional change recording.
* PostgreSQL forced row-level security, composite project/tenant references and a restricted runtime identity. Startup rejects a privileged database identity or missing RLS.
* A working React interface, Tauri shell configuration and native system-browser PKCE sign-in source.

Read [setup and operation](docs/SETUP.md), [acceptance evidence and limitations](docs/PHASE_1_STATUS.md), and [feature contracts](docs/FOUNDATION_CONTRACTS.md). The reviewed REST contract is [OpenAPI JSON](packages/api-contracts/openapi.json); development API documentation is at `/docs`.

## Current acceptance status

Backend and browser foundation checks pass. The native release executable now compiles, passes four native tests and opens its demonstration sign-in screen on Windows. NSIS installer packaging now succeeds after the documented x64 compiler repair. Installation/uninstallation and live production identity-provider acceptance remain pending. See [Windows build report](docs/WINDOWS_BUILD_REPORT.md). This is a development foundation, not a released subscription product. Do not treat the entire phase as accepted until those checks are complete.

No source-controlled credentials are included. Local demonstration identity must never be enabled on a shared or public server. SQLite is reserved for Android in Phase 4; all Phase 1 database tests use real PostgreSQL.

## Source layout

`services/api` contains domain endpoints, schemas, immutable migrations and PostgreSQL integration tests. `apps/desktop` contains the React interface, Tauri shell and UI checks. `infra/local` contains privileged local role provisioning. `tools` contains contract export, safe secret generation and a non-destructive synthetic restore check. `.github/workflows` describes backend and Windows validation; it has not been executed on a hosted runner in this session.

## Technology decisions

SQLAlchemy/Alembic provide PostgreSQL access and migration history; PyJWT/cryptography validate provider signatures; pytest exercises the domain/security boundaries. React/Vite/TypeScript provide the client, with Vitest for client API checks and Playwright for user workflows. `oidc-client-ts` handles browser-preview PKCE. Native PKCE uses reqwest for HTTPS, tokio for bounded loopback callback handling, url for parsing, rand/sha2/base64 for PKCE and state, and open for the system browser. No passwords or refresh tokens are persisted by the desktop client. Libraries have lockfiles where resolved locally; Native dependencies are resolved in Cargo.lock and Rust is pinned in rust-toolchain.toml.

## Boundaries

Calendars are definitions in Phase 1, not a CPM engine. There is no schedule, baseline, progress, AI, drawing, billing or cloud deployment implementation yet. No emails are sent; invitation tokens are copied securely by an administrator. Production identity configuration and cloud data location remain operator decisions. Request permission before starting Phase 2 after resolving Phase 1 acceptance gaps.
