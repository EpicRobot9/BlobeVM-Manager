#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string] $InstallRoot = 'C:\ProgramData\EpicVM\agent',
    [int] $Port = 8765,
    [string] $TailscaleAddress
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$sourceRoot = $PSScriptRoot
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'providers') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'logs') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'vms') -Force | Out-Null

$tokenPath = Join-Path $InstallRoot 'agent.token'
if (Test-Path -LiteralPath $tokenPath) {
    $token = (Get-Content -LiteralPath $tokenPath -Raw -Encoding UTF8).Trim()
}
else {
    $bytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    Set-Content -LiteralPath $tokenPath -Value $token -Encoding ascii -NoNewline
}

$agentPath = Join-Path $InstallRoot 'EpicVM.Agent.ps1'
$providerPath = Join-Path $InstallRoot 'providers/HyperVProvider.ps1'
Copy-Item -LiteralPath (Join-Path $sourceRoot 'EpicVM.Agent.ps1') -Destination $agentPath -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot 'providers/HyperVProvider.ps1') -Destination $providerPath -Force
$configPath = Join-Path $InstallRoot 'config.json'
if ([string]::IsNullOrWhiteSpace($TailscaleAddress)) {
    $tailscaleAddresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -match '^100\.(6[4-9]|[7-9][0-9])\.' } |
        Select-Object -ExpandProperty IPAddress)
    if ($tailscaleAddresses.Count -eq 1) {
        $TailscaleAddress = [string]$tailscaleAddresses[0]
    }
}
if ([string]::IsNullOrWhiteSpace($TailscaleAddress) -or $TailscaleAddress -notmatch '^100\.(6[4-9]|[7-9][0-9])\.(\d{1,3})\.(\d{1,3})$') {
    throw 'A single Tailscale IPv4 address is required. Pass -TailscaleAddress 100.x.y.z.'
}
$config = [ordered]@{
    BindAddress = $TailscaleAddress
    Port = $Port
    Provider = 'HyperV'
    TokenFile = $tokenPath
    ConfigFile = $configPath
    VmRoot = (Join-Path $InstallRoot 'vms')
    SwitchName = ''
    DefaultMemoryBytes = 4294967296
    DefaultCpuCount = 2
    DefaultDiskSizeBytes = 68719476736
    MinMemoryBytes = 536870912
    MaxMemoryBytes = 17179869184
    MinCpuCount = 1
    MaxCpuCount = 16
    MaxDiskSizeBytes = 549755813888
    Generation = 2
}
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8

# Keep the credential readable only by LocalSystem and local administrators.
$acl = Get-Acl -LiteralPath $tokenPath
$acl.SetAccessRuleProtection($true, $false)
$acl.Access | ForEach-Object { [void]$acl.RemoveAccessRule($_) }
foreach ($identity in @('SYSTEM', 'Administrators')) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($identity, 'Read', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $tokenPath -AclObject $acl

$serviceName = 'EpicVMRemoteAgent'
$pwsh = (Get-Command pwsh -ErrorAction Stop).Source
$binPath = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}" -ConfigPath "{2}"' -f $pwsh, $agentPath, $configPath
$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne 'Stopped') { Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue }
    sc.exe config $serviceName binPath= $binPath start= auto | Out-Null
}
else {
    New-Service -Name $serviceName -DisplayName 'EpicVM RemoteVM Agent' -Description 'EpicVM Hyper-V VM lifecycle agent' -BinaryPathName $binPath -StartupType Automatic | Out-Null
}

# Do not expose the API to the public network. Tailscale uses 100.64.0.0/10.
$ruleName = 'EpicVM RemoteVM Agent (Tailscale)'
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress '100.64.0.0/10' -Profile Any | Out-Null
Start-Service -Name $serviceName

$healthUri = "http://$TailscaleAddress`:$Port/v1/health"
$healthy = $false
for ($attempt = 0; $attempt -lt 10; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri $healthUri -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 2 -ErrorAction Stop
        if ($health.ok -eq $true) { $healthy = $true; break }
    }
    catch { Start-Sleep -Seconds 1 }
}
if (-not $healthy) {
    throw 'EpicVM RemoteVM agent did not pass its local health check after installation.'
}

Write-Output "EpicVM RemoteVM agent installed: $serviceName"
Write-Output "Agent endpoint: http://<tailscale-host>:${Port}/v1/health"
Write-Output "Token file: $tokenPath"
Write-Output 'Enrollment token is stored in the protected token file and is not printed.'
