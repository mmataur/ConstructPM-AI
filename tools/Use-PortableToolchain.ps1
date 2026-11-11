param([Parameter(Mandatory=$true)][string]$ToolchainRoot)
# Dot-source this file. All settings affect this PowerShell process only.
$toolRoot=(Resolve-Path -LiteralPath $ToolchainRoot).Path
$vcTools=Get-ChildItem -LiteralPath (Join-Path $toolRoot 'msvc\VC\Tools\MSVC') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$sdkRoot=Join-Path $toolRoot 'sdk\10'
$sdkVersion=Get-ChildItem -LiteralPath (Join-Path $sdkRoot 'Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1
if (-not $vcTools -or -not $sdkVersion) { throw 'Portable Microsoft compiler/SDK not ready' }
$compilerBin=Join-Path $vcTools.FullName 'bin\Hostx64\x64'
$sdkBin=Join-Path $sdkRoot ('bin\'+$sdkVersion.Name+'\x64')
$env:PATH=(Join-Path $toolRoot 'portable\bin')+';'+$compilerBin+';'+$sdkBin+';'+$env:PATH
$env:CARGO_HOME=Join-Path $toolRoot 'cargo'
$env:CARGO_BUILD_JOBS='2'
$env:CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=Join-Path $compilerBin 'link.exe'
$env:VCINSTALLDIR=(Join-Path $toolRoot 'msvc\VC')+'\'
$env:VCToolsInstallDir=$vcTools.FullName+'\'
$env:WindowsSdkDir=$sdkRoot+'\'
$env:WindowsSDKVersion=$sdkVersion.Name+'\'
$env:UniversalCRTSdkDir=$sdkRoot+'\'
$env:UCRTVersion=$sdkVersion.Name
$env:VSCMD_ARG_TGT_ARCH='x64'
$env:VSCMD_ARG_HOST_ARCH='x64'
$env:Platform='x64'
$env:CC='cl.exe'
$env:CXX='cl.exe'
$env:INCLUDE=(Join-Path $vcTools.FullName 'include')+';'+((@('ucrt','shared','um','winrt','cppwinrt') | ForEach-Object { Join-Path $sdkRoot ('Include\'+$sdkVersion.Name+'\'+$_) }) -join ';')
$env:LIB=(Join-Path $vcTools.FullName 'lib\x64')+';'+(Join-Path $sdkRoot ('Lib\'+$sdkVersion.Name+'\ucrt\x64'))+';'+(Join-Path $sdkRoot ('Lib\'+$sdkVersion.Name+'\um\x64'))
Write-Output 'Workspace-local Rust, Microsoft compiler and Windows SDK selected.'
