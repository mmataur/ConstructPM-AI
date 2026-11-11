# Setup and operation

Run these commands from the extracted `ConstructPM_AI` repository unless another folder is specified. Install project dependencies in the project environment. Never use the demonstration identity on a public/shared service.

## 1. Prerequisites

* Python 3.12, Node 24 LTS with npm, and PostgreSQL 17 with `psql`, `pg_dump` and `pg_restore` available.
* For a Windows native build: Rust stable MSVC toolchain, Visual Studio Build Tools with Desktop development with C++ and Windows SDK, and WebView2. The local build used workspace-local official compiler/SDK payloads. A native executable was built and launched; NSIS installer packaging now succeeds after the repair in NSIS_COMPILER_FIX.md. See WINDOWS_BUILD_REPORT.md.
* Production: a public/native OIDC application with authorization code + PKCE, RS256-signed API JWT access tokens, the configured API audience, and `sub`, `email`, `email_verified=true`, `iss`, `aud`, `iat`, `exp` claims. Configure MFA at the provider. Some providers need a custom API claim mapping for verified email. Do not substitute an ID token for an API access token.

Official prerequisite reference: [Tauri Windows prerequisites](https://tauri.app/start/prerequisites/).

## 2. Backend environment

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r services\api\requirements.lock.txt
Copy-Item .env.example .env
```

Generate a random local `DEV_AUTH_SECRET` of at least 32 characters, or use `tools/New-LocalSecret.ps1` instead of copying an existing `.env`. Fill in the database credentials. Keep `.env` private and out of version control. Examples intentionally contain no working password. The local allowlist contains `planner@example.test` and `supervisor@example.test`; these are synthetic identities only.

## 3. Privileged PostgreSQL provisioning

Use a local PostgreSQL administrator. Start an existing database server bound to loopback for local development; choose its port and use that port consistently. The examples below use 55432. The provisioning file creates fresh roles and database and is intentionally not rerunnable over an existing installation. It never drops data.

```powershell
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres -v ON_ERROR_STOP=1 -f infra/local/provision.sql
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres
```

Inside psql, run `\password constructpm_app` to set a strong application password without putting it into shell history, then `\q`. Use SCRAM authentication for persisted/shared environments. Do not copy the ephemeral test server's trust authentication into deployment. The `constructpm_policy` role is NOLOGIN with BYPASSRLS solely for narrowly defined read-only membership helper functions. The runtime role cannot inherit it or change its functions. This provisioning requires administrator-level PostgreSQL privileges; it is not the identity the API uses.

Apply migrations with an administrator/migration identity that can install the RLS helper functions and assign their dedicated owner:

```powershell
$env:MIGRATION_DATABASE_URL = 'postgresql+psycopg://postgres:YOUR_PASSWORD@127.0.0.1:55432/constructpm'
Set-Location services\api
..\..\.venv\Scripts\python -m alembic upgrade head
Set-Location ..\..
```

URL-encode password characters in a database URL. Remove the migration credential from the API runtime environment. `.env` must use `constructpm_app`, not the migration administrator. Startup fails if the app role is privileged, owns public tables, has policy-role membership, lacks forced RLS, or is at the wrong schema revision.

## 4. Start the local API

```powershell
Set-Location services\api
..\..\.venv\Scripts\python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --env-file ..\..\.env
```

Keep this terminal running. `/health` is process liveness; startup validates the database identity and schema. `/docs` provides development API documentation. Both real and local identity modes use bearer tokens for protected endpoints.

## 5. Desktop interface and Windows shell

In another terminal:

```powershell
Set-Location apps\desktop
npm ci
npm run dev
```

Open `http://127.0.0.1:1420` for the browser preview. Sign in with a clearly marked local identity, register a company, create a project, save a calendar, then invite/assign another local identity. No invitation email is sent. Copy the single-use token securely and accept it while signed in as the invited email.

After the native Windows prerequisites are installed:

```powershell
npm run tauri info
npm run tauri dev
npm run tauri build
```

The unsigned installer output normally appears under `src-tauri/target/release/bundle/nsis`. This source includes an icon, scoped capabilities, Cargo.lock and a pinned Rust version. Native deliveries now include a standalone executable/ZIP and a setup executable. The setup is unsigned and has not been installed/uninstalled. A commercial release also requires code signing, trusted update distribution and installer acceptance testing; none has occurred here.

## 6. Configure real identity

Backend settings: `ENVIRONMENT=production`, `DEV_AUTH=false`, trusted HTTPS `OIDC_ISSUER`, `OIDC_JWKS_URL`, and API `OIDC_AUDIENCE`. Frontend `apps/desktop/.env` needs `VITE_OIDC_ISSUER`, public `VITE_OIDC_CLIENT_ID`, and HTTPS `VITE_API_URL`. Configure API CORS to the actual bundled-client/browser origins, and change Tauri's `connect-src` to the exact deployed HTTPS API. Rebuild after frontend/config changes. No client secret belongs in frontend settings.

Browser preview callback is its origin `/`, e.g. `http://127.0.0.1:1420/`. Native sign-in opens the system browser and receives the authorization code at `http://127.0.0.1:<ephemeral-port>/callback`; the provider must support loopback redirect ports for a public native app. State and S256 PKCE bind the callback/exchange. Native access tokens stay in application memory; no refresh token is requested or saved. Closing/reloading the app requires sign-in again. Provider logout is separate from application sign-out. Verify this flow with the chosen provider before marking authentication accepted for production.

## 7. Automated checks

Create a separate database ending `_test` with the same roles. Migrate it; never point tests at project/customer data:

```powershell
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres -c 'CREATE DATABASE constructpm_test'
$env:MIGRATION_DATABASE_URL = 'postgresql+psycopg://postgres:YOUR_PASSWORD@127.0.0.1:55432/constructpm_test'
$env:TEST_DATABASE_URL = 'postgresql+psycopg://constructpm_app:YOUR_APP_PASSWORD@127.0.0.1:55432/constructpm_test'
$env:TEST_ADMIN_PASSWORD = 'YOUR_POSTGRES_TEST_ADMIN_PASSWORD'
Set-Location services\api
..\..\.venv\Scripts\python -m alembic upgrade head
..\..\.venv\Scripts\python -m pytest -q
Set-Location ..\..\apps\desktop
npm test
npm run build
npm audit
npx playwright install chromium
npx playwright test
```

Playwright requires the local API and preview to be running, with the two standard demo identities enabled. It creates synthetic companies and leaves their audit history intact. An already installed Chrome can be used via `PLAYWRIGHT_EXECUTABLE_PATH`. Run native `cargo test` from `apps/desktop/src-tauri` once its toolchain is available. CI describes these checks but was not executed remotely here.

## 8. Backup and recovery

For local synthetic verification:

```powershell
$env:RECOVERY_SOURCE_URL = 'postgresql+psycopg://postgres:YOUR_PASSWORD@127.0.0.1:55432/constructpm_test'
$env:PG_BIN = 'C:\Path\To\PostgreSQL\bin'
$env:RECOVERY_APP_PASSWORD = 'YOUR_APP_PASSWORD'
.venv\Scripts\python tools\recovery_check.py
```

The tool only accepts a synthetic `_test` source, creates a uniquely named restore database, performs custom-format dump/restore, compares all table rows and policy definitions, and verifies no-context denial with the restricted runtime role. It never drops databases. It leaves the restore database for inspection and writes `work/recovery/recovery-result.json`; remove the synthetic database later only after explicitly checking its name and confirming it is no longer needed.

For deployment, define encrypted backups, WAL/PITR retention, separate credentials, key recovery and restore access. Restore to an isolated environment, verify schema, row counts/hashes and RLS, then run application access tests before switching service traffic. A failed migration rolls back its transaction; destructive downgrades are intentionally blocked. Do not restore over a live database. Phase 6 must test actual cloud recovery times and, once introduced, object-storage consistency. This local drill does not establish a production RPO/RTO.

## 9. Troubleshooting and limitations

* 401: expired/untrusted token or provider claims/audience mismatch; sign in again and inspect safe provider configuration, never log raw tokens.
* 404 company/project: wrong selected company, missing assignment or revoked access; hidden scope is intentional.
* 412: refresh the record before resubmitting; the write was not applied.
* Connection lost during a create: refresh before retrying, because generic online POST replay receipts are not implemented yet.
* Startup role/schema rejection: run migrations with a separate privileged identity, then use the restricted runtime identity.
* Missing native tools: install the documented Windows prerequisites; a successful browser build does not validate Tauri/Rust.
* PostgreSQL helpers must retain their NOLOGIN read-only policy owner; changing ownership can break RLS or cause recursion. Do not grant the app policy-role membership.

Stop API and preview with Ctrl+C. Stop a locally managed PostgreSQL server cleanly with its normal service manager or `pg_ctl stop -m fast`. This project does not install a system service or modify the user's machine-wide development configuration.

## Workspace-local build helpers

`tools/Build-Windows.ps1` supports `-Action Test`, `Build` (release executable without bundling), and `Bundle` (attempt NSIS). With a normal Windows development setup, use it from the repository root. For the prepared local environment, pass `-ToolchainRoot` pointing to the existing `work/toolchain` folder in the chat workspace and `-NpmCliPath` pointing to `work/npm/package/bin/npm-cli.js`. These helpers change only the calling process environment. They do not install machine-wide tools. Native release tests use the same custom-protocol feature as the packaged app.
