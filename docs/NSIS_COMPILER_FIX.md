# NSIS installer compiler repair

## Diagnosis

The original cached NSIS 3.13 compiler failed even when invoked with `/VERSION`, before reading any ConstructPM installer script. Windows returned error 623 (Illegal System DLL Relocation). The bundled compiler was an x86 PE executable depending on `MSVCP60.dll`, `MSVCRT.dll` and an x86 `zlib1.dll`, among other Windows libraries. A separate Windows x86 command processor did run, so the evidence does **not** establish that all 32-bit programs are unsupported. The precise conflicting DLL/address was not identified.

This localized the failure to the bundled compiler's startup/DLL-loading environment rather than the application or installer script. Rebuilding the same NSIS 3.13 source for x64 with the available modern Microsoft toolchain removed that startup failure. No Windows security, ASLR or DLL-loading protections were disabled.

## Inputs

* Official [NSIS v313 source](https://github.com/NSIS-Dev/nsis/tree/v313), archive `https://github.com/NSIS-Dev/nsis/archive/refs/tags/v313.zip`, SHA-256 `c4b08ca7c064252dbd3bb1ba28430c0e4571e7f888bfffb62259d301b3d2b0e2` for the archive used here.
* Official [zlib v1.3.1 source](https://github.com/madler/zlib/tree/v1.3.1), archive `https://github.com/madler/zlib/archive/refs/tags/v1.3.1.zip`, SHA-256 `50b24b47bf19e1f35d2a21ff36d2a366638cdf958219a66f30ce0861201760e6` for the archive used here.
* SCons 4.11.1, installed only in the development environment. See `tools/windows-build-requirements.txt`.
* Existing workspace-local Microsoft x64 C++ compiler and Windows SDK, selected through `Use-PortableToolchain.ps1`.

Do not include SCons or the compiler sources in production API dependencies. The x64 compiler is a build tool; installer stubs/plugins retain their original Tauri-compatible x86 Unicode format, and the installed ConstructPM executable remains x64.

## Reproduction

Use a fresh extracted NSIS source tree, a trusted x64 developer environment and the original complete Tauri NSIS cache (including Stubs, Include and Plugins). Preserve original compiler/DLL files before replacing them. All operations used here were confined to the workspace.

1. Build zlib from its source directory with `nmake /nologo /f win32/Makefile.msc zlib1.dll`. This creates the x64 zlib DLL and `zdll.lib` with the selected x64 compiler.
2. For this portable compiler environment, adapt NSIS `SConstruct`'s initial construction environment to inherit `dict(os.environ)`, set `MSVC_USE_SCRIPT=False`, and set `MSVC_VERSION`/`MSVS_VERSION` to `14.3`. This supplies the already configured compiler paths instead of probing for a machine-wide Visual Studio installation. Normal Visual Studio setups may not require this adaptation.
3. Keep `TARGET_ARCH=amd64` for the compiler binary, but write `NSIS_DEFAULT_TARGET_ARCH "x86"` in the generated configuration. This preserves the original installer-stub/plugin target while running a 64-bit compiler.
4. In `Source/build.cpp`, for the non-constant-data-path branch of `CEXEBuild::initialize`, use `get_executable_dir(makensis_path)` as `nsis_dir`, instead of its parent. This compiler is placed at Tauri's NSIS package root rather than inside `Bin`. Tauri explicitly removes `NSISDIR` and `NSISCONFDIR` from the compiler environment, so an environment-only workaround is insufficient.
5. Build the compiler target using the following options (substitute the absolute zlib path):

```text
python -m SCons -j4 TOOLSET=msvc,mslink,mslib,masm,msvs TARGET_ARCH=amd64 SKIPSTUBS=all SKIPPLUGINS=all SKIPUTILS=all SKIPMISC=all VERSION=3.13 ZLIB_W32=<absolute-zlib-source-path> NSIS_CONFIG_CONST_DATA_PATH=no build/urelease/makensis/makensis.exe
```

6. Place the resulting x64 compiler at `apps/desktop/src-tauri/target/.tauri/NSIS/makensis.exe`, and its matching x64 `zlib1.dll` beside it. Preserve the complete original Stubs/Include/Plugins directories. No compiler rebuild of those installer components is needed.
7. Clear `NSISDIR` and `NSISCONFDIR` in a child environment, then run the root compiler with `/VERSION`. The repaired tool must report `v3.13` with exit code 0. Verify its PE machine is `0x8664`, not `0x014c`.
8. Rerun `tools/Build-Windows.ps1 -Action Bundle` with the same prepared toolchain and npm CLI paths used for the successful native executable build.

The original x86 compiler files were preserved under the chat workspace's `work/nsis-original`. They are not shipped in the application delivery. Deleting Tauri's cached NSIS directory restores the standard downloaded tool on the next bundle attempt, so reapply this repair if the same startup failure recurs after clearing caches.

This repair does not install the generated application or prove installation/uninstallation. Those are separate acceptance checks. Code signing and production identity/API configuration remain outside this installer-build repair.

References: [official NSIS build instructions](https://nsis.sourceforge.io/Docs/AppendixG.html), [Tauri NSIS bundler implementation](https://github.com/tauri-apps/tauri/blob/dev/crates/tauri-bundler/src/bundle/windows/nsis/mod.rs).

## Verified outcome

The full Tauri bundle command completed with exit code 0 and produced a 2,947,956-byte setup executable. The delivery is ConstructPM_AI_0.1.0_Setup.exe; its hash is recorded in installer-verification.json. Installation/uninstallation and code signing remain pending. The x86 NSIS installer launcher contains the x64 ConstructPM application.
