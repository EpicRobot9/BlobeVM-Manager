# Requires -Version 7.0
<#
    EpicVM RemoteVM host agent.

    The script is both a small HTTP service and a dot-sourceable request
    dispatcher.  Pester tests use -NoStart and call Invoke-EpicVMApiRequest
    directly, while the Windows service calls Start-EpicVMAgent.
#>

[CmdletBinding()]
param(
    [switch] $NoStart,
    [string] $ConfigPath = (Join-Path $PSScriptRoot 'config.json'),
    [string] $BindAddress,
    [int] $Port = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$providerPath = Join-Path $PSScriptRoot 'providers/HyperVProvider.ps1'
if (Test-Path -LiteralPath $providerPath) {
    . $providerPath
}

function Get-EpicVMDefaultConfig {
    return [pscustomobject]@{
        BindAddress = '0.0.0.0'
        Port = 8765
        Provider = 'HyperV'
        TokenFile = 'C:\ProgramData\EpicVM\agent\agent.token'
        ConfigFile = 'C:\ProgramData\EpicVM\agent\config.json'
        VmRoot = 'C:\ProgramData\EpicVM\vms'
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
}

function Get-EpicVMProperty {
    param(
        [AllowNull()] [object] $Object,
        [Parameter(Mandatory)] [string] $Name,
        [AllowNull()] [object] $Default = $null
    )
    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary]) {
        foreach ($key in $Object.Keys) {
            if ([string]::Equals([string]$key, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $Object[$key]
            }
        }
        return $Default
    }
    foreach ($property in $Object.PSObject.Properties) {
        if ([string]::Equals($property.Name, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $property.Value
        }
    }
    return $Default
}

function Read-EpicVMConfig {
    param([Parameter(Mandatory)] [string] $Path)
    $defaults = Get-EpicVMDefaultConfig
    if (-not (Test-Path -LiteralPath $Path)) { return $defaults }
    try {
        $loaded = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw 'The EpicVM agent configuration is invalid JSON.'
    }
    foreach ($property in $defaults.PSObject.Properties) {
        $value = Get-EpicVMProperty -Object $loaded -Name $property.Name -Default $property.Value
        $defaults.$($property.Name) = $value
    }
    return $defaults
}

function Get-EpicVMAgentToken {
    param([Parameter(Mandatory)] [object] $Config)
    $token = [string](Get-EpicVMProperty -Object $Config -Name 'Token' -Default '')
    if ($token) { return $token.Trim() }
    $tokenPath = [string](Get-EpicVMProperty -Object $Config -Name 'TokenFile' -Default '')
    if (-not $tokenPath -or -not (Test-Path -LiteralPath $tokenPath)) {
        throw 'The EpicVM agent token file is missing.'
    }
    $token = (Get-Content -LiteralPath $tokenPath -Raw -Encoding UTF8).Trim()
    if (-not $token) { throw 'The EpicVM agent token file is empty.' }
    return $token
}

function Test-EpicVMBearerToken {
    param(
        [AllowNull()] [string] $ProvidedToken,
        [AllowNull()] [string] $ExpectedToken
    )
    if ([string]::IsNullOrEmpty($ProvidedToken) -or [string]::IsNullOrEmpty($ExpectedToken)) { return $false }
    $left = [Text.Encoding]::UTF8.GetBytes($ProvidedToken)
    $right = [Text.Encoding]::UTF8.GetBytes($ExpectedToken)
    if ($left.Length -ne $right.Length) { return $false }
    return [Security.Cryptography.CryptographicOperations]::FixedTimeEquals($left, $right)
}

function Test-EpicVMName {
    param([AllowNull()] [string] $Name)
    if ($null -eq $Name) { return $false }
    return [regex]::IsMatch($Name, '\A[a-z0-9][a-z0-9._-]{0,62}\z', [Text.RegularExpressions.RegexOptions]::CultureInvariant)
}

function New-EpicVMAgentState {
    param(
        [Parameter(Mandatory)] [object] $Config,
        [Parameter(Mandatory)] [string] $Token,
        [Parameter(Mandatory)] [object] $Provider
    )
    return [pscustomobject]@{
        Config = $Config
        Token = $Token
        Provider = $Provider
        StartedAt = [DateTime]::UtcNow
    }
}

function New-EpicVMApiError {
    param([Parameter(Mandatory)] [string] $Code, [Parameter(Mandatory)] [string] $Message)
    return [ordered]@{ ok = $false; error = [ordered]@{ code = $Code; message = $Message } }
}

function ConvertTo-EpicVMJsonResponse {
    param(
        [Parameter(Mandatory)] [int] $StatusCode,
        [Parameter(Mandatory)] [object] $Body
    )
    return [pscustomobject]@{
        StatusCode = $StatusCode
        Body = $Body
        Json = ($Body | ConvertTo-Json -Depth 16 -Compress)
    }
}

function Get-EpicVMHeader {
    param([AllowNull()] [object] $Headers, [Parameter(Mandatory)] [string] $Name)
    if ($null -eq $Headers) { return '' }
    if ($Headers -is [System.Collections.IDictionary]) {
        foreach ($key in $Headers.Keys) {
            if ([string]::Equals([string]$key, $Name, [System.StringComparison]::OrdinalIgnoreCase)) { return [string]$Headers[$key] }
        }
    }
    return [string](Get-EpicVMProperty -Object $Headers -Name $Name -Default '')
}

function Get-EpicVMRequestBody {
    param([AllowNull()] [object] $Body)
    if ($null -eq $Body -or $Body -eq '') { return @{} }
    if ($Body -is [string]) {
        try { return ($Body | ConvertFrom-Json -AsHashtable) } catch { throw 'Request body is not valid JSON.' }
    }
    if ($Body -is [System.Collections.IDictionary]) { return $Body }
    return $Body
}

function New-EpicVMProvider {
    param(
        [Parameter(Mandatory)] [object] $Config,
        [AllowNull()] [scriptblock] $CommandInvoker = $null
    )
    switch ([string](Get-EpicVMProperty -Object $Config -Name 'Provider' -Default 'HyperV')) {
        'HyperV' {
            return New-EpicVMHyperVProvider -Config $Config -CommandInvoker $CommandInvoker
        }
        default {
            throw ("Unsupported provider: {0}" -f (Get-EpicVMProperty -Object $Config -Name 'Provider' -Default ''))
        }
    }
}

function Get-EpicVMProviderCapabilities {
    param([Parameter(Mandatory)] [object] $Provider)
    try {
        $capabilities = & $Provider.GetCapabilities
        if ($capabilities -is [System.Collections.IDictionary]) { return $capabilities }
        return [ordered]@{ provider = [string]$Provider.Name; available = $false; features = @() }
    }
    catch {
        return [ordered]@{ provider = [string]$Provider.Name; available = $false; features = @(); error = 'provider_unavailable' }
    }
}

function Invoke-EpicVMProviderAction {
    param(
        [Parameter(Mandatory)] [object] $Provider,
        [Parameter(Mandatory)] [string] $Action,
        [Parameter(Mandatory)] [string] $Name,
        [AllowNull()] [object] $Request = @{}
    )
    switch ($Action.ToLowerInvariant()) {
        'start' { return (& $Provider.StartVM $Name) }
        'stop' { return (& $Provider.StopVM $Name) }
        'restart' { return (& $Provider.RestartVM $Name) }
        'delete' { return (& $Provider.DeleteVM $Name) }
        default { throw "Unsupported VM action: $Action" }
    }
}

function Invoke-EpicVMApiRequest {
    param(
        [Parameter(Mandatory)] [object] $State,
        [Parameter(Mandatory)] [ValidateSet('GET', 'POST', 'DELETE')] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        [AllowNull()] [object] $Headers = @{},
        [AllowNull()] [object] $Body = $null
    )
    $authorization = Get-EpicVMHeader -Headers $Headers -Name 'Authorization'
    $provided = ''
    if ($authorization -match '^Bearer\s+(.+)$') { $provided = $Matches[1].Trim() }
    if (-not (Test-EpicVMBearerToken -ProvidedToken $provided -ExpectedToken ([string]$State.Token))) {
        return ConvertTo-EpicVMJsonResponse -StatusCode 401 -Body (New-EpicVMApiError -Code 'unauthorized' -Message 'Authentication required.')
    }

    $normalizedPath = '/' + $Path.Trim('/')
    $segments = @($normalizedPath.Trim('/').Split('/') | Where-Object { $_ -ne '' } | ForEach-Object { [Uri]::UnescapeDataString($_) })
    try {
        if ($Method -eq 'GET' -and $normalizedPath -eq '/v1/health') {
            return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body ([ordered]@{ ok = $true; status = 'ok'; agent = 'EpicVM'; provider = [string]$State.Provider.Name })
        }
        if ($Method -eq 'GET' -and $normalizedPath -eq '/v1/capabilities') {
            $caps = Get-EpicVMProviderCapabilities -Provider $State.Provider
            $caps.ok = $true
            return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body $caps
        }
        if ($Method -eq 'GET' -and $segments.Count -eq 2 -and $segments[0] -eq 'v1' -and $segments[1] -eq 'vms') {
            $vms = @(& $State.Provider.GetVMs)
            return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body ([ordered]@{ ok = $true; vms = $vms })
        }
        if ($Method -eq 'POST' -and $segments.Count -eq 2 -and $segments[0] -eq 'v1' -and $segments[1] -eq 'vms') {
            $request = Get-EpicVMRequestBody -Body $Body
            $name = [string](Get-EpicVMProperty -Object $request -Name 'name' -Default (Get-EpicVMProperty -Object $request -Name 'Name' -Default ''))
            if (-not (Test-EpicVMName -Name $name)) {
                return ConvertTo-EpicVMJsonResponse -StatusCode 400 -Body (New-EpicVMApiError -Code 'invalid_name' -Message 'The VM name is invalid.')
            }
            $vm = & $State.Provider.CreateVM $request
            return ConvertTo-EpicVMJsonResponse -StatusCode 201 -Body ([ordered]@{ ok = $true; vm = $vm })
        }
        if ($segments.Count -ge 3 -and $segments[0] -eq 'v1' -and $segments[1] -eq 'vms') {
            $name = $segments[2]
            if (-not (Test-EpicVMName -Name $name)) {
                return ConvertTo-EpicVMJsonResponse -StatusCode 400 -Body (New-EpicVMApiError -Code 'invalid_name' -Message 'The VM name is invalid.')
            }
            if ($Method -eq 'GET' -and $segments.Count -eq 3) {
                $vms = @(& $State.Provider.GetVMs)
                $vm = @($vms | Where-Object { [string](Get-EpicVMProperty -Object $_ -Name 'name' -Default '') -eq $name }) | Select-Object -First 1
                if ($null -eq $vm) { return ConvertTo-EpicVMJsonResponse -StatusCode 404 -Body (New-EpicVMApiError -Code 'not_found' -Message 'The requested VM was not found.') }
                return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body ([ordered]@{ ok = $true; vm = $vm })
            }
            if ($Method -eq 'GET' -and $segments.Count -eq 4 -and $segments[3] -eq 'logs') {
                return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body ([ordered]@{ ok = $true; logs = ''; supported = $false })
            }
            if ($Method -eq 'POST' -and $segments.Count -eq 5 -and $segments[3] -eq 'actions') {
                $result = Invoke-EpicVMProviderAction -Provider $State.Provider -Action $segments[4] -Name $name
                return ConvertTo-EpicVMJsonResponse -StatusCode 200 -Body ([ordered]@{ ok = $true; vm = $result })
            }
        }
        return ConvertTo-EpicVMJsonResponse -StatusCode 404 -Body (New-EpicVMApiError -Code 'not_found' -Message 'Route not found.')
    }
    catch {
        $errorCode = [string](Get-EpicVMProperty -Object $_.Exception -Name 'ErrorCode' -Default 'provider_error')
        $message = [string]$_.Exception.Message
        if ($message -match 'token|authorization|secret|password') { $message = 'The provider request failed.' }
        $status = if ($errorCode -eq 'NotFound') { 404 } elseif ($errorCode -in @('InvalidInput', 'Conflict')) { 400 } elseif ($errorCode -eq 'UnmanagedVM') { 403 } else { 502 }
        return ConvertTo-EpicVMJsonResponse -StatusCode $status -Body (New-EpicVMApiError -Code $errorCode.ToLowerInvariant() -Message $message)
    }
}

function Start-EpicVMAgent {
    param(
        [Parameter(Mandatory)] [object] $State,
        [string] $Bind = '0.0.0.0',
        [int] $ListenPort = 8765
    )
    $listener = [Net.HttpListener]::new()
    # The listener is intentionally reachable on the host's interfaces; the
    # installer restricts TCP/8765 to the Tailscale CGNAT range in Windows Firewall.
    $listener.Prefixes.Add("http://+:$ListenPort/")
    try { $listener.Start() } catch { throw 'Unable to start the EpicVM agent listener. Run the installer as an administrator.' }
    Write-Verbose ("EpicVM remote agent listening on {0}:{1}" -f $Bind, $ListenPort)
    try {
        while ($listener.IsListening) {
            $context = $listener.GetContext()
            try {
                $headers = @{}
                foreach ($key in $context.Request.Headers.AllKeys) { $headers[$key] = $context.Request.Headers[$key] }
                $body = $null
                if ($context.Request.HasEntityBody) {
                    $reader = [IO.StreamReader]::new($context.Request.InputStream, [Text.Encoding]::UTF8)
                    try { $body = $reader.ReadToEnd() } finally { $reader.Dispose() }
                }
                $response = Invoke-EpicVMApiRequest -State $State -Method $context.Request.HttpMethod -Path $context.Request.Url.AbsolutePath -Headers $headers -Body $body
                $bytes = [Text.Encoding]::UTF8.GetBytes($response.Json)
                $context.Response.StatusCode = $response.StatusCode
                $context.Response.ContentType = 'application/json; charset=utf-8'
                $context.Response.ContentLength64 = $bytes.Length
                $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
            }
            catch {
                $body = (New-EpicVMApiError -Code 'internal_error' -Message 'The agent could not process the request.') | ConvertTo-Json -Depth 10 -Compress
                $bytes = [Text.Encoding]::UTF8.GetBytes($body)
                $context.Response.StatusCode = 500
                $context.Response.ContentType = 'application/json; charset=utf-8'
                $context.Response.ContentLength64 = $bytes.Length
                $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
            }
            finally { $context.Response.Close() }
        }
    }
    finally { $listener.Stop(); $listener.Close() }
}

if (-not $NoStart) {
    $config = Read-EpicVMConfig -Path $ConfigPath
    if ($BindAddress) { $config.BindAddress = $BindAddress }
    if ($Port -gt 0) { $config.Port = $Port }
    $token = Get-EpicVMAgentToken -Config $config
    $providerConfig = @{}
    foreach ($property in $config.PSObject.Properties) { $providerConfig[$property.Name] = $property.Value }
    switch ([string]$config.Provider) {
        'HyperV' { $provider = New-EpicVMHyperVProvider -Config $providerConfig }
        default { throw ("Unsupported provider: {0}" -f $config.Provider) }
    }
    $state = New-EpicVMAgentState -Config $config -Token $token -Provider $provider
    Start-EpicVMAgent -State $state -Bind ([string]$config.BindAddress) -ListenPort ([int]$config.Port)
}
