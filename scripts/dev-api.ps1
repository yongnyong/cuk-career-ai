param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'api'
$pythonPath = Join-Path $apiRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create api/.venv and install api/requirements-dev.txt first. See docs/LOCAL_DEVELOPMENT.md.'
}

# Pin this process to the local database even if the parent shell has DATABASE_URL.
$databasePath = (Join-Path $apiRoot 'dev.db').Replace('\', '/')
$env:DATABASE_URL = 'sqlite:///' + $databasePath
$careerDatabasePath = (Join-Path $apiRoot 'career.db').Replace('\', '/')
$env:CAREER_DATABASE_URL = 'sqlite:///' + $careerDatabasePath
$env:COOKIE_SECURE = '0'
$env:PYTHONUTF8 = '1'
$env:CAREER_LOCAL_AI = '1'
if (-not $env:CAREER_AI_PROVIDER) { $env:CAREER_AI_PROVIDER = 'codex' }

Push-Location $apiRoot
try {
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
    if ($LASTEXITCODE -ne 0) { throw "API exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
