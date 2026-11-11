# Phase 1 implementation and acceptance report

11 November 2026. User authorized Phase 1 only. No Phase 2 work, deployment, billing, email delivery or production account provisioning was performed.

## Outcome

The PostgreSQL/FastAPI foundation and React desktop interface are implemented and locally verified. Tauri release compilation, four native helper tests and native sign-in-screen launch are now verified. NSIS installer packaging now passes after the documented compiler repair. Installation/uninstallation, full native workflow and a live organization identity-provider flow remain unverified. See WINDOWS_BUILD_REPORT.md. **Overall Phase 1 acceptance remains open until these gaps are resolved.** No native feature is marked complete based on a browser build.

## Verification performed

| Check | Result | Evidence / practical scope |
|---|---|---|
| Backend suite | PASS â€” 33 cases | Real PostgreSQL 17.6 with restricted `constructpm_app`, not SQLite and not database administrator |
| Authentication | PASS at API verifier level | Invalid tokens, expiration/issuer/audience/verified-email checks; RSA signature, foreign signing key and algorithm substitution; dev identity disabled for production |
| Company/tenant isolation | PASS | Separate companies, guessed project IDs, hidden data, raw-SQL missing-context denial and pooled connection context reset |
| Roles and membership | PASS | All eight project roles, nonadmin denial, invitation email/expiry/replay, membership deactivation, project-access revocation and concurrent last-admin demotions |
| Stale edits | PASS | If-Match required; stale row versions rejected; forbidden tenant-field input rejected |
| Calendar definitions | PASS | Ordered shifts, weekday completeness, timezone/date validation, separate immutable versions; runtime mutation denied |
| Audit evidence | PASS | Transactional events, request IDs, newest-first cursor pagination, invalid cursor handling and mutation denial |
| Unsafe runtime configuration | PASS | Startup rejects privileged database identities; requires forced RLS and expected schema revision |
| Database migrations | PASS | Empty database through both migrations; existing populated revision 0001 upgraded to 0002; repeated upgrade reaches same head without reapplying |
| Recovery drill | PASS | Custom-format dump to a fresh synthetic database; all nine public tables match counts/content hashes; policy definitions match; restricted-role no-context denial survives restore |
| Client API tests | PASS â€” 2 cases | Credentials/version header placement and surfaced 412 failure |
| TypeScript and browser production bundle | PASS | `npm run build`; 34 transformed modules, approximately 316 kB JS before gzip |
| Browser end-to-end workflow | PASS â€” 1 scenario | Company â†’ project â†’ two calendar versions â†’ invitation â†’ acceptance as other identity â†’ supervisor assignment â†’ read-only calendar â†’ audit visibility |
| Visual check | PASS for inspected view | Overview at 1440 px; real rendered browser screenshot inspected. This is not native Windows/WebView2 visual approval. |
| npm dependency advisory check | PASS | Zero reported vulnerabilities at this session's audit; this does not guarantee future dependency security |
| Native environment check | PASS locally | Workspace-local official Rust/Cargo, Microsoft C++ and Windows SDK payloads; installed WebView2 |
| Native Rust tests and executable | PASS | Four helper tests passed; Cargo.lock generated; release executable opened its demo sign-in screen |
| Native installer build | PASS | Repaired x64 NSIS compiler produced a verified setup executable; install/uninstall not yet tested |
| Hosted CI | NOT RUN | Workflow source supplied; no remote repository or hosted runner configured |
| Actual production OIDC provider | NOT RUN | No issuer/client registration/tenant supplied; synthetic RSA verifies API behavior but does not replace provider integration acceptance |

The backend run emits one Starlette deprecation warning about its HTTPX TestClient integration. It does not fail tests; align the test transport with a maintained supported version before a production release. No performance/load or penetration-test claim is made.

## Delivered feature boundaries

Company registration, invitations, organization and project roles, project creation/edit/archiving, independent project-access revocation, calendar definition/versioning, audit and database isolation are functional. Desktop access tokens stay in memory; reload/expiry requires sign-in. Provider session logout, refresh-token storage, commercial SSO provisioning and account-recovery UX depend on the chosen identity provider and have not been added.

Calendar definitions are not working-time calculations. CPM, baselines, actuals, scenarios, approvals, mobile synchronization, file storage, workers, take-offs, AI and subscription billing remain in their authorized future phases. No physical progress, resource recovery or forecast dates are fabricated.

## Remaining Phase 1 acceptance work

1. Finish native account/project/calendar acceptance using the built executable. Validate installation/uninstallation of the generated installer; packaging itself now passes. The local compiler/SDK setup, locked dependencies, native tests and sign-in-screen launch are now complete; this is still an unsigned demonstration build.
2. Select/configure the production identity provider and public client, then verify system-browser PKCE, expected JWT claims/audience, MFA policy, sign-in cancellation/timeout, expiry and application sign-out. Configure deployed HTTPS API origin and CSP.
3. Run the supplied CI on the owning repository and resolve any platform-specific issues. No GitHub repository was created or code pushed.
4. Review the feature contracts and demonstrate the native foundation before authorizing the next major phase.

## Known limitations to track

* Generic online POST replay receipts are not implemented; writes are not automatically retried. After an ambiguous network failure, refresh before resubmission. Android durable operation receipts remain Phase 4.
* Membership/calendar list endpoints are unbounded and should be paginated for large tenants.
* The calendar editor handles weekly shifts and nonworking exceptions; custom work-date exceptions are supported by API and preserved by the editor, but do not yet have their own edit controls.
* No cloud service, monitoring stack, production backup schedule, object storage or production RPO/RTO was configured. The local restore drill covers only the Phase 1 database.
* The local test server is ephemeral, loopback-bound and uses trust authentication for synthetic data only. Its binaries/data/secrets are outside the source delivery. Follow setup instructions for SCRAM-protected persistent environments.
* No independent security audit, sustained load benchmark, Windows native accessibility review or live production pilot has occurred.

These limitations do not authorize work in Phase 2. The next work should close the remaining Phase 1 acceptance checks.
