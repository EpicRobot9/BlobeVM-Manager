# Requires -Version 7.0
# Requires -Modules Pester

BeforeAll {
    $windowsRoot = Split-Path -Parent $PSScriptRoot
    . (Join-Path $windowsRoot 'EpicVM.Agent.ps1') -NoStart

    function New-TestProvider {
        [pscustomobject]@{
            Name = 'Mock'
            GetCapabilities = { @{ provider = 'Mock'; available = $true; features = @('lifecycle') } }
            GetVMs = { @(@{ name = 'alpha'; state = 'Off'; managed = $true }) }
            CreateVM = { param($request) @{ name = $request.Name; state = 'Off'; managed = $true } }
            StartVM = { param($name) @{ name = $name; state = 'Running'; managed = $true } }
            StopVM = { param($name) @{ name = $name; state = 'Off'; managed = $true } }
            RestartVM = { param($name) @{ name = $name; state = 'Running'; managed = $true } }
            DeleteVM = { param($name) @{ name = $name; deleted = $true } }
        }
    }
}

Describe 'EpicVM agent authentication' {
    It 'compares bearer tokens without accepting a near match' {
        Test-EpicVMBearerToken -ProvidedToken 'correct-token' -ExpectedToken 'correct-token' | Should -BeTrue
        Test-EpicVMBearerToken -ProvidedToken 'correct-toke' -ExpectedToken 'correct-token' | Should -BeFalse
        Test-EpicVMBearerToken -ProvidedToken 'correct-tokenx' -ExpectedToken 'correct-token' | Should -BeFalse
        Test-EpicVMBearerToken -ProvidedToken '' -ExpectedToken 'correct-token' | Should -BeFalse
    }

    It 'requires the bearer token and never echoes it in the error response' {
        $state = New-EpicVMAgentState -Config (Get-EpicVMDefaultConfig) -Token 'test-secret-token' -Provider (New-TestProvider)
        $response = Invoke-EpicVMApiRequest -State $state -Method 'GET' -Path '/v1/health' -Headers @{ Authorization = 'Bearer wrong-token' }

        $response.StatusCode | Should -Be 401
        ($response.Body | ConvertTo-Json -Depth 10) | Should -Not -Match 'test-secret-token'
        ($response.Body | ConvertTo-Json -Depth 10) | Should -Not -Match 'wrong-token'
    }
}

Describe 'EpicVM agent capabilities and routing' {
    BeforeEach {
        $config = Get-EpicVMDefaultConfig
        $config.Provider = 'Mock'
        $script:state = New-EpicVMAgentState -Config $config -Token 'test-secret-token' -Provider (New-TestProvider)
    }

    It 'returns JSON-ready capabilities for an authenticated request' {
        $response = Invoke-EpicVMApiRequest -State $state -Method 'GET' -Path '/v1/capabilities' -Headers @{ Authorization = 'Bearer test-secret-token' }

        $response.StatusCode | Should -Be 200
        $response.Body.provider | Should -Be 'Mock'
        $response.Body.available | Should -BeTrue
    }

    It 'rejects unknown routes with a clean JSON error' {
        $response = Invoke-EpicVMApiRequest -State $state -Method 'GET' -Path '/v1/does-not-exist' -Headers @{ Authorization = 'Bearer test-secret-token' }

        $response.StatusCode | Should -Be 404
        $response.Body.error.code | Should -Be 'not_found'
    }

    It 'validates VM names against the public contract' {
        foreach ($name in @('alpha', 'dev.box-01', 'a' * 63)) {
            Test-EpicVMName -Name $name | Should -BeTrue
        }

        foreach ($name in @('', 'Aalpha', '-alpha', 'alpha/', 'a' * 64, 'alpha name')) {
            Test-EpicVMName -Name $name | Should -BeFalse
        }
    }
}

Describe 'EpicVM provider selection' {
    It 'selects the configured Hyper-V adapter and rejects unknown providers' {
        $config = Get-EpicVMDefaultConfig
        $config.Provider = 'HyperV'
        $provider = New-EpicVMProvider -Config $config -CommandInvoker { param($commandName, $parameters) @() }
        $provider.Name | Should -Be 'HyperV'

        $config.Provider = 'OtherProvider'
        { New-EpicVMProvider -Config $config } | Should -Throw '*Unsupported provider*'
    }
}
