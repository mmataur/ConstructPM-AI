param([string]$OutputPath = ".env")
if (Test-Path -LiteralPath $OutputPath) { throw "Output exists. Preserve its secrets or choose a new path." }
$secretBytes = New-Object byte[] 48
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($secretBytes) } finally { $rng.Dispose() }
$secret = [Convert]::ToBase64String($secretBytes)
$content = @"
ENVIRONMENT=development
DEV_AUTH=true
DEV_AUTH_SECRET=$secret
DEV_EMAILS=planner@example.test,supervisor@example.test
DATABASE_URL=postgresql+psycopg://constructpm_app:REPLACE_PASSWORD@127.0.0.1:55432/constructpm
"@
Set-Content -LiteralPath $OutputPath -Value $content -Encoding utf8
Write-Output "Local settings created. Set your database password before starting the API. Keep this file private."

