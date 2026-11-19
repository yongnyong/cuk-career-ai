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

# Windows can hold Next's dev lock exclusively. Identify the listener by its CLI parent.
$devLock = Join-Path $webRoot '.next\dev\lock'
if ((Test-Path -LiteralPath $devLock) -and -not $PSBoundParameters.ContainsKey('ApiPort')) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0') }
    foreach ($listener in $listeners) {
        $server = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($server.Name -ne 'node.exe') { continue }
        $cli = Get-CimInstance Win32_Process -Filter "ProcessId = $($server.ParentProcessId)" -ErrorAction SilentlyContinue
        if ($cli.CommandLine -match '\sdev(?:\s|$)' -and $cli.CommandLine.IndexOf($nextPath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            Write-Host "CUK Career AI is already running: http://127.0.0.1:$Port/tree"
            return
        }
    }
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
