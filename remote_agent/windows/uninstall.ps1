#Requires -RunAsAdministrator
[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $InstallRoot = 'C:\ProgramData\EpicVM\agent',
    [int] $Port = 8765,
    [switch] $PurgeData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$serviceName = 'EpicVMRemoteAgent'
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $serviceName | Out-Null
}
Get-NetFirewallRule -DisplayName 'EpicVM RemoteVM Agent (Tailscale)' -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
if ($PurgeData) {
    if ($PSCmdlet.ShouldProcess($InstallRoot, 'Remove EpicVM agent data')) {
        Remove-Item -LiteralPath $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
else {
    Write-Output "EpicVM agent service removed. Data retained at $InstallRoot."
}
