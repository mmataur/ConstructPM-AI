# Phase 1 feature contracts

These contracts define the implemented foundation and its acceptance scope. API paths are relative to `/api/v1`; organization paths begin `/organizations/{o}`. A company is an organization/tenant. IDs are stable UUID strings. The API never trusts a client-supplied role or tenant context to establish authority.

| Feature | Purpose and dependencies | Data/API | User experience | Acceptance criteria |
|---|---|---|---|---|
| Identity | Establish a verified principal; requires configured OIDC issuer/JWKS/audience, or explicitly enabled local development mode | `users`; `GET /me`, `GET /auth/config`; local-only `POST /dev/token` | Secure sign-in; visible local-demo banner; token held in memory | Invalid/expired/wrong-audience/wrong-issuer/unsigned/unverified-email tokens rejected; production cannot enable dev mode; trusted RSA key checked |
| Company registration | Bootstrap isolated company; verified principal and migrated database | `organizations`, `memberships`; `POST /organizations`, `GET /organizations` | Company form, timezone, company switcher | Organization + first admin + audit commit together; discovery returns only own active memberships |
| Company membership | Delegate access without privilege escalation; registration and verified email | `invitations`, `memberships`; create invitation, accept, versioned membership PATCH | Invite/accept forms; role and activation controls | Exact verified email; three-day expiry; single use; last admin remains; self-deactivation requires another admin; nonadmin cannot invite or change company roles |
| Project foundation | Define project and access boundaries; active company membership | `projects`, `project_memberships`; project CRUD subset and assignment endpoints | Project creation/details/archiving; explicit project-role assignment | Cross-company guessed IDs hidden; unassigned projects hidden; eight roles enforced; archived projects retained; stale edits return 412 |
| Calendars | Preserve working-time definitions for future engine; project access and valid timezone | `calendar_versions`; list/create/new-version POST | Weekly shifts, duration-day minutes, nonworking-date editor | ISO weekdays complete; ordered nonoverlapping shifts; exceptions validated; referenced versions immutable; only admin/PM/planner can author |
| Audit | Trace authorized changes; transactional database | `audit_events`; paginated administrator read | Audit history with actor/time/action/detail | Business changes and audit commit atomically; runtime cannot update/delete evidence; scope enforced |
| Desktop shell | Make foundation usable; API and client dependencies | React routes/state and Tauri source | Overview/projects/calendars/people/audit; inaccessible controls hidden | Browser workflow passes; keyboard-usable controls; backend authority independent of UI; native build still pending |
| Migration/recovery | Reproduce schema and preserve records; privileged provisioning separated from runtime | Frozen Alembic SQL, forced policies, dump/restore tool | Operator procedures | Empty DB migration and repeated upgrade pass; synthetic restore matches rows/policies; restricted role still denied without context |

## Access matrix

Company administrator: register/create projects, invite and manage company users, assign/update project roles, create calendars, view company audit. Administrator status does not grant future approval permissions automatically.

Project manager: read assigned project/calendars and edit project name/archive state and calendar versions. Planner: read assigned project and author calendar versions. Site engineer, supervisor, quantity surveyor, executive, subcontractor and guest: read explicitly assigned project/calendars in Phase 1; their future progress/take-off features do not exist yet. Every company member may register a separate company; membership does not grant access to another member's company.

Project managers cannot assign roles in this initial implementation. An organization administrator assigns and changes project roles. Project access can be revoked or restored independently without removing the company membership; the project membership record remains for history. No application endpoint deletes historical records.

## Concurrency and integrity

Mutable project and membership changes require `If-Match: "<row_version>"`; no header returns 428, stale version returns 412. Membership changes take a tenant-scoped transaction advisory lock and recheck administrative authority. Calendar version creation serializes numbering on the parent project. All identity/tenant values are parameterized SQL inputs. Transaction-local settings are reset automatically on commit/rollback; a missing context denies project rows. Composite foreign keys include organization/project IDs.

POST creation currently has no generic replay/idempotency receipt. The UI disables submissions while pending and performs no automatic retry of writes. If a connection drops after commit, refresh before resubmitting. Durable offline operation receipts remain Phase 4; generic online command receipts should be added before production release. There is no automatic schedule publication in Phase 1.

## Calendar semantics

ISO weekday 1=Monday, 7=Sunday. Local shifts are `[start,end)` HH:MM pairs; `24:00` can terminate a shift. Split overnight shifts across days. Date exceptions override the weekly pattern: `[]` is nonworking; the API also accepts replacement work intervals. The initial desktop editor edits weekly shifts and nonworking exceptions, retaining existing custom working exceptions unchanged. The API supports those custom exceptions directly. Nominal duration-day minutes are explicit and do not mean 24 elapsed hours. Phase 2 must resolve DST ambiguity and implement actual working-time arithmetic; Phase 1 validation alone is not CPM/calendar arithmetic verification.

## Errors and data handling

401 unauthenticated; 403 action denied; 404 inaccessible/missing scope; 409 conflict; 412 stale; 422 invalid; 428 missing version. Errors contain request IDs and safe field messages; validation payloads omit submitted values. Lists are paged where project/audit volume is expected. Membership/calendar collections are currently unbounded; cap or paginate before large production tenants. Access tokens are in-memory and reauthentication is required after reload/expiry. Sign-out clears the application session, not necessarily the provider's browser session.
