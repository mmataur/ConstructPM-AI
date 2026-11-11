# Native Windows build verification

11 November 2026. Scope: build and launch the Phase 1 Windows desktop demonstration. Phase 2 remains unauthorized and has not been started.

## Results

| Check | Result |
|---|---|
| Rust/compiler/SDK preparation | PASS â€” workspace-local tools; no successful machine-wide installation |
| Locked native dependency resolution | PASS â€” Cargo.lock committed; Rust toolchain pinned |
| Native release tests | PASS â€” 4 tests, 0 failures |
| Frontend type-check and production assets | PASS |
| Client API tests | PASS â€” 2 tests |
| Tauri release compilation | PASS â€” `constructpm-desktop.exe`, x86-64 Windows |
| Native launch | PASS â€” window titled ConstructPM AI, bundled page at `http://tauri.localhost/` |
| Native service reachability | PASS at sign-in screen â€” both development identities loaded from the running API; no connection error shown |
| Native account/project/calendar workflow | NOT YET VERIFIED â€” browser workflow was previously verified; do not equate it with native acceptance |
| NSIS setup packaging | BLOCKED â€” makensis.exe failed with Windows error 623 / Illegal System DLL Relocation |
| Installer install/uninstall | NOT RUN â€” no valid installer was produced |
| Real OIDC provider flow | NOT RUN â€” provider/client configuration still required |
| Code signing / production deployment | NOT RUN |

The built executable was copied into the separate `ConstructPM_AI_Windows` delivery folder and opened with a workspace-local WebView2 profile. Its sign-in screen was read through native Windows accessibility. No real identity-provider authentication dialog was automated. The existing PostgreSQL project data was not recreated or replaced.

## Toolchain and provenance

* Rust 1.99.1 / Cargo 1.99.1, x86_64-pc-windows-msvc, from the official Rust stable distribution. Component archive SHA-256 values matched the official channel manifest.
* Microsoft C/C++ compiler 19.44.35230, toolset folder 14.44.35207, from official Visual Studio release-catalog payloads.
* Windows SDK 10.0.26100.0 headers, x64 libraries and resource tools, from official Microsoft SDK packages. Package/cabinet SHA-256 values matched the Visual Studio catalog.
* Node 24.22.1; Tauri CLI 2.12.4; native Tauri crate 2.12.5, locked in Cargo.lock. Vite and frontend dependencies remain locked in package-lock.json.

The standard Rust installer could not create its proxy links in this execution environment; Microsoft setup also returned a requirements error. Official payloads were therefore extracted into the permitted workspace rather than modifying system installation folders. This does not install a globally available compiler or SDK. The helper `tools/Use-PortableToolchain.ps1` selects those local tools for a single PowerShell process; normal supported machine installations can still use the standard documented workflow.

The frontend build hook now runs Node directly through `build.mjs`, so native packaging does not depend on a globally installed npm launcher. Bundling tools are cached under the project target directory through `bundle.useLocalToolsDir`.

## Native test result

Command: `cargo test --release --features custom-protocol --locked`

```text
running 4 tests
tests::requires_https ... ok
tests::parses_one_valid_callback ... ok
tests::rejects_duplicate_codes ... ok
tests::rejects_bad_callback_state ... ok
test result: ok. 4 passed; 0 failed
```

These are native OIDC helper tests, not a live provider sign-in test.

## Build and packaging result

`tools/Build-Windows.ps1 -Action Bundle` successfully completed the Tauri release compilation and produced the application executable. Tauri then downloaded and hash-validated NSIS 3.13 and its Tauri helper plugin. The initial 32-bit NSIS compiler could not start because Windows reported error 623. Rebuilding NSIS 3.13 for x64 and adapting its package-root lookup resolved the failure; the full bundle command then succeeded. The executable itself was subsequently launched successfully; both the portable ZIP and a separately generated setup executable are now available. See NSIS_COMPILER_FIX.md and installer-verification.json.

`tools/Build-Windows.ps1 -Action Build` was also run successfully: Tauri completed `build --no-bundle` with exit code 0. Use `-Action Build` to reproduce the release executable without attempting an installer. Use `-Action Bundle` with the repaired compiler, or the standard compiler on another compatible machine, then validate installation/uninstallation before acceptance. Do not disable Windows security or DLL-loading protections to force this build environment to run NSIS.

The application remains configured for the loopback demonstration API and development identities. A production build needs HTTPS API/CSP/CORS settings, a real public/native OIDC client, signing and deployment validation.

References: [Tauri prerequisites](https://tauri.app/start/prerequisites/), [Windows packaging](https://v2.tauri.app/distribute/windows-installer/), [project-local bundler tools](https://v2.tauri.app/reference/config/#uselocaltoolsdir), [Rust installation](https://rust-lang.org/tools/install/).
