param(
    [ValidateRange(1, 65535)]
    [int]$Port = 3000,
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 8000
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot 'web'
$nextPath = Join-Path $webRoot 'node_modules\next\dist\bin\next'
if (-not (Test-Path -LiteralPath $nextPath)) {
    throw 'Install web dependencies first (cd web; npm ci). See docs/LOCAL_DEVELOPMENT.md.'
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $nodePath = $nodeCommand.Source
}
else {
    # PyCharm may not inherit the Node path provided to the Codex terminal.
    $nodePath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (-not (Test-Path -LiteralPath $nodePath)) {
        throw 'Node.js was not found. Install Node.js 20.9 or newer and restart your terminal.'
    }
}

$env:API_URL = "http://127.0.0.1:$ApiPort"
$env:NEXT_TELEMETRY_DISABLED = '1'

Push-Location $webRoot
try {
    & $nodePath $nextPath dev --hostname 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Web server exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
