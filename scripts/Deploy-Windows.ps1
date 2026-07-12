[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$DashboardOnly,
    [string]$WslDistribution
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Dashboard = Join-Path $Root 'dashboard_v2'

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Missing required command: $Name" }
}

Require-Command 'node.exe'
Require-Command 'npm.cmd'
Write-Host 'Building Dashboard v2 release on Windows...'
Push-Location $Dashboard
try {
    if (-not (Test-Path (Join-Path $Dashboard 'node_modules'))) {
        npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    }
    else {
        Write-Host 'Using the existing dependency tree; fresh deployment checkouts use npm ci.'
    }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed' }
}
finally { Pop-Location }

if ($DashboardOnly) {
    Write-Host "Dashboard release is ready at $Dashboard\dist"
    exit 0
}

Require-Command 'wsl.exe'
$WslArgs = @()
if ($WslDistribution) { $WslArgs += @('--distribution', $WslDistribution) }
$WslRoot = (& wsl.exe @WslArgs wslpath -a ($Root -replace '\\','/')).Trim()
if ($LASTEXITCODE -ne 0 -or -not $WslRoot) { throw 'Could not translate the repository path into WSL.' }

$Preflight = "cd '$WslRoot' && command -v bash && command -v docker && docker compose version && bash -n scripts/Deploy-Linux.sh server/install.sh"
& wsl.exe @WslArgs bash -lc $Preflight
if ($LASTEXITCODE -ne 0) { throw 'WSL preflight failed. Enable Docker Desktop WSL2 integration and systemd.' }

if ($CheckOnly) {
    Write-Host 'Windows/WSL2 deployment preflight passed. No host changes were made.'
    exit 0
}

Write-Host 'Handing off to the supported Linux installer inside WSL2...'
$Deploy = "cd '$WslRoot' && sudo bash scripts/Deploy-Linux.sh"
& wsl.exe @WslArgs bash -lc $Deploy
if ($LASTEXITCODE -ne 0) { throw "WSL deployment failed with exit code $LASTEXITCODE" }
