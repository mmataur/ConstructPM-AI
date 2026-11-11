param(
    [ValidateSet('Test','Build','Bundle')][string]$Action='Test',
    [string]$ToolchainRoot,
    [string]$NpmCliPath
)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
if ($NpmCliPath) {
    $NpmCliPath=(Resolve-Path -LiteralPath $NpmCliPath).Path
    $env:PATH=(Split-Path $NpmCliPath -Parent)+';'+$env:PATH
}
if ($ToolchainRoot) { . (Join-Path $PSScriptRoot 'Use-PortableToolchain.ps1') -ToolchainRoot $ToolchainRoot }
function Invoke-Npm([string[]]$Arguments) {
    if ($NpmCliPath) { & node $NpmCliPath @Arguments } else { & npm.cmd @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "Frontend/build command failed: $LASTEXITCODE" }
}
Push-Location (Join-Path $repoRoot 'apps\desktop')
try {
    if ($Action -eq 'Test') {
        Invoke-Npm @('run','build')
        Invoke-Npm @('test')
        Push-Location 'src-tauri'
        try { & cargo test --release --features custom-protocol --locked; if ($LASTEXITCODE -ne 0) { throw 'Native tests failed' } }
        finally { Pop-Location }
    } elseif ($Action -eq 'Build') {
        Invoke-Npm @('run','tauri','build','--','--no-bundle')
    } else {
        Invoke-Npm @('run','tauri','build')
    }
} finally { Pop-Location }
