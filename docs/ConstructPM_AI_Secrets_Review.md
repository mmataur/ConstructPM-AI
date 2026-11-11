# ConstructPM AI — sensitive-information review

Reviewed 11 November 2026. Read-only review; no credentials, source code or runtime settings were changed.

## Result

No production API keys, private-key blocks or literal JWT credentials were detected in the application source or delivered source ZIP. Password-like values do exist: test credentials, example placeholders, a schema-export helper's dummy signing key, and a real local-development signing secret in runtime settings outside the source package.

This is a targeted source/artifact review, not a guarantee that every possible secret format has been detected or a general security certification.

## Findings

| Classification | Location | Finding |
|---|---|---|
| Sensitive local runtime value | The chat workspace's `work/local.env`, line 3 | A real 64-character development JWT signing secret is present. Value withheld. It is outside the application source and was not found in the source/demo ZIPs, unbundled frontend assets or raw executable/installer bytes. Keep the runtime file private; rotate this demo secret if the whole workspace has been shared. |
| Test-only passwords | `.github/workflows/foundation.yml`, lines 10, 14–17 and 27 | Fixed database passwords are used for disposable CI test services. These are not production credentials. They must not be reused in deployed database configuration. |
| Test-only signing key | `services/api/tests/conftest.py`, line 18 | A fixed dummy signing key is used by the isolated test app. No production secret was found here. |
| Schema-export dummy key | `tools/export_openapi.py`, line 8 | A fixed dummy signing key permits construction of an app object for OpenAPI export. The script exports schemas rather than serving a live API. Do not run this app object as a deployed authentication service. |
| Dummy token/test values | `apps/desktop/src/api.test.ts`; `services/api/tests/test_oidc.py` | Credential-like strings are deliberate fixtures. RSA keys in the test are generated at runtime rather than embedded as private keys. |
| Example placeholders | `.env.example`, lines 4, 6–7; `docs/SETUP.md`; `tools/New-LocalSecret.ps1` | Placeholder signing/database values and replacement-password examples. No live database password was detected in these examples. |
| Configuration hardening needed | `.env.example:4` and `services/api/app/config.py:19` | The example signing-secret placeholder is exactly 32 characters. Development validation checks only minimum length and environment, so copying the example unchanged is accepted. This was confirmed by calling validation without starting the API. Reject known placeholders in validation and use a randomly generated local value. Production mode already rejects development authentication. |

## Other sensitive-information checks

* Identity-provider issuer, audience, JWKS URL and native public-client ID settings are configuration/public identifiers, not client secrets. No embedded OIDC client secret was detected.
* Runtime authentication reads the signing secret from the environment. No production fallback signing key was detected.
* The local demonstration database URL contains no password; the local demonstration uses trust-based database access as documented. This is development configuration and must not be carried into production.
* Demo email addresses, company/project labels, local paths, record IDs and checksums appear in test/demo documentation. They are not authentication secrets, but review business identifiers before publishing the project publicly.
* The source ZIP contains no `.env`, private-key, PFX/P12 or credentials-file entries matching the inspected names. The real local runtime settings file is not included.

## Coverage and limitations

Reviewed 61 UTF-8 text source/configuration/documentation files, including Rust source and lockfiles, while excluding dependency trees and generated build caches. Scans covered common provider-key formats, private-key markers, JWT literals, database connection strings and credential-related assignments; suspicious assignments were manually checked in their owning files.

The source ZIP was scanned after decompression. The exact known local development signing-secret value was compared against source files, unbundled frontend files, every entry of the source and portable-demo ZIPs, and raw bytes of the delivered application and setup executable. No match was found. Raw binary scanning does not inspect every possible encrypted/compressed resource; frontend/source checks provide the stronger evidence about this known value.

No Git repository/history is available for this application folder, so deleted or previously committed secrets could not be assessed. Third-party dependencies, every scratch log/database file, external service accounts and private browser/session stores were not comprehensively audited. The entire `work` folder should not be distributed as application source.

## Recommended next steps

1. Keep the real local runtime secret private and out of delivered source; rotate it only if it has been exposed.
2. Reject known example placeholders in development-secret validation.
3. Preserve test-only isolation; never reuse fixture passwords or signing keys in production.
4. Add a maintained secret scanner to repository checks when the project is placed under version control.
