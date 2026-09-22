[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'start', 'seed', 'test', 'proof', 'demo', 'logs', 'stop', 'reset')]
    [string]$Action = 'start',
    [switch]$ConfirmReset,
    [PSCredential]$Credential
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ComposeFile = Join-Path $ProjectRoot 'compose.yaml'
$EnvFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw 'compose.yaml não encontrado na raiz de Gestão de recebíveis.'
}
if ((Get-Content -LiteralPath $ComposeFile -Raw) -notmatch '(?m)^name: pf-gestao-recebiveis\s*$') {
    throw 'O script só pode operar o projeto Compose pf-gestao-recebiveis.'
}

function New-LocalSecret {
    $Bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($Bytes)
    return [Convert]::ToHexString($Bytes).ToLowerInvariant()
}

function Initialize-Environment {
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        $SecretBytes = New-Object byte[] 48
        $Random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $Random.GetBytes($SecretBytes) } finally { $Random.Dispose() }
        $SessionSecret = [Convert]::ToBase64String($SecretBytes).Replace('+', '-').Replace('/', '_')
        $DatabaseBytes = New-Object byte[] 48
        $DatabaseRandom = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $DatabaseRandom.GetBytes($DatabaseBytes) } finally { $DatabaseRandom.Dispose() }
        $DatabasePassword = [Convert]::ToBase64String($DatabaseBytes).Replace('+', '-').Replace('/', '_')
        $Template = Get-Content -LiteralPath (Join-Path $ProjectRoot '.env.example') -Raw
        $Template = $Template.Replace('REPLACE_WITH_RANDOM_SECRET', $SessionSecret)
        $Template = $Template.Replace('REPLACE_WITH_RANDOM_DATABASE_PASSWORD', $DatabasePassword)
        $Template = $Template.Replace('REPLACE_WITH_RANDOM_OWNER_PASSWORD', (New-LocalSecret))
        $Template = $Template.Replace('REPLACE_WITH_RANDOM_APP_PASSWORD', (New-LocalSecret))
        [System.IO.File]::WriteAllText($EnvFile, $Template, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host '.env criado.'
    }
    # Upgrade preserves the original bootstrap password and database volume.
    $Existing = Get-Content -LiteralPath $EnvFile -Raw
    foreach ($Key in @('DATABASE_OWNER_PASSWORD', 'DATABASE_APP_PASSWORD')) {
        if ($Existing -notmatch "(?m)^$Key=.+$") {
            [System.IO.File]::AppendAllText($EnvFile, "`n$Key=$(New-LocalSecret)`n", [System.Text.UTF8Encoding]::new($false))
        }
    }
}

function Invoke-CobraCompose {
    param([string[]]$ComposeArgs)
    & docker compose --project-directory $ProjectRoot --env-file $EnvFile -f $ComposeFile -p pf-gestao-recebiveis @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose falhou (código $LASTEXITCODE): $($ComposeArgs -join ' ')"
    }
}

function Invoke-IsolatedCompose {
    param([string[]]$ComposeArgs)
    $IsolatedFile = Join-Path $ProjectRoot 'compose.e2e.yaml'
    & docker compose --project-directory $ProjectRoot --env-file $EnvFile -f $ComposeFile -f $IsolatedFile -p pf-gestao-recebiveis-e2e @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose E2E isolado falhou (código $LASTEXITCODE): $($ComposeArgs -join ' ')"
    }
}

function Get-CobraConfiguration {
    $ConfigurationJson = & docker compose --project-directory $ProjectRoot --env-file $EnvFile -f $ComposeFile -p pf-gestao-recebiveis config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao validar o Compose.' }
    return ($ConfigurationJson | ConvertFrom-Json)
}

function Assert-LocalPorts {
    $Configuration = Get-CobraConfiguration
    foreach ($ServiceName in @('api', 'frontend')) {
        $PublishedPort = [int]$Configuration.services.$ServiceName.ports[0].published
        $OwnBindings = & docker ps --filter 'label=com.docker.compose.project=pf-gestao-recebiveis' --filter "label=com.docker.compose.service=$ServiceName" --format '{{.Ports}}'
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao listar os containers do projeto.' }
        if (($OwnBindings -join '') -match "127\.0\.0\.1:$PublishedPort->") { continue }
        $Probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $PublishedPort)
        $Probe.Server.ExclusiveAddressUse = $true
        try { $Probe.Start() }
        catch { throw "Porta $PublishedPort ocupada. Ajuste API_PORT ou FRONTEND_PORT/FRONTEND_ORIGIN no .env." }
        finally { $Probe.Stop() }
    }
}

function Start-Application {
    Assert-LocalPorts
    Invoke-CobraCompose -ComposeArgs @('up', '-d', '--wait', '--wait-timeout', '180', 'db', 'api', 'worker', 'frontend')
}

Get-Command docker -ErrorAction Stop | Out-Null
& docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Engine indisponível. Inicie o Docker Desktop.' }
Initialize-Environment

switch ($Action) {
    'proof' { & (Join-Path $PSScriptRoot 'prove.ps1') }
    'setup' {
        Assert-LocalPorts
        foreach ($BuildService in @('db', 'api', 'frontend')) {
            Invoke-CobraCompose -ComposeArgs @('build', $BuildService)
        }
        Invoke-CobraCompose -ComposeArgs @('up', '-d', '--wait', 'db')
        Invoke-CobraCompose -ComposeArgs @('run', '--rm', 'migrate')
        Invoke-CobraCompose -ComposeArgs @('run', '--rm', '--no-deps', 'seed')
        Start-Application
    }
    'start' { Start-Application }
    'seed' {
        Invoke-CobraCompose -ComposeArgs @('up', '-d', '--wait', 'db')
        Invoke-CobraCompose -ComposeArgs @('run', '--rm', 'migrate')
        Invoke-CobraCompose -ComposeArgs @('run', '--rm', '--no-deps', 'seed')
    }
    'test' {
        try {
            foreach ($BuildService in @('db', 'api', 'frontend', 'frontend-checks', 'e2e')) {
                Invoke-CobraCompose -ComposeArgs @('build', $BuildService)
            }
            Invoke-CobraCompose -ComposeArgs @('run', '--rm', 'test')
            Invoke-CobraCompose -ComposeArgs @('up', '-d', '--wait', '--force-recreate', 'db-upgrade-test')
            Invoke-CobraCompose -ComposeArgs @('run', '--rm', '--no-deps', 'upgrade-test')
            Invoke-CobraCompose -ComposeArgs @('run', '--rm', '--no-deps', 'frontend-checks')
            Invoke-IsolatedCompose -ComposeArgs @('up', '-d', '--wait', 'db')
            Invoke-IsolatedCompose -ComposeArgs @('run', '--rm', 'migrate')
            Invoke-IsolatedCompose -ComposeArgs @('run', '--rm', '--no-deps', 'seed')
            Invoke-IsolatedCompose -ComposeArgs @('up', '-d', '--wait', '--wait-timeout', '180', 'api', 'worker', 'frontend')
            Invoke-IsolatedCompose -ComposeArgs @('run', '--rm', '--no-deps', 'e2e')
        }
        finally {
            Invoke-IsolatedCompose -ComposeArgs @('--profile', 'test', '--profile', 'tools', 'down', '--remove-orphans')
            Invoke-CobraCompose -ComposeArgs @('stop', 'db-test', 'db-upgrade-test')
        }
    }
    'demo' {
        Start-Application
        Invoke-CobraCompose -ComposeArgs @('run', '--rm', '--no-deps', 'seed')
        Get-Content -LiteralPath (Join-Path $ProjectRoot 'docs/demo.md')
    }
    'logs' { Invoke-CobraCompose -ComposeArgs @('logs', '--tail', '150', '-f', 'api', 'worker', 'frontend') }
    'stop' { Invoke-CobraCompose -ComposeArgs @('--profile', 'test', '--profile', 'tools', 'down', '--remove-orphans') }
    'reset' {
        if (-not $ConfirmReset -or $null -eq $Credential) {
            throw 'Reset exige -ConfirmReset e -Credential (Get-Credential operador@example.com). Remove somente dados de demonstração deste projeto.'
        }
        $Configuration = Get-CobraConfiguration
        if ($Configuration.name -ne 'pf-gestao-recebiveis' -or $Configuration.services.api.environment.DEMO_MODE -ne 'true' -or $Configuration.services.db.environment.POSTGRES_DB -ne 'gestao_recebiveis') {
            throw 'Reset recusado: o alvo precisa ser pf-gestao-recebiveis/gestao_recebiveis em DEMO_MODE=true.'
        }
        Invoke-CobraCompose -ComposeArgs @('stop', 'api', 'worker')
        $RunningServices = & docker compose --project-directory $ProjectRoot --env-file $EnvFile -f $ComposeFile -p pf-gestao-recebiveis ps --services --status running
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao confirmar API e worker parados.' }
        if ($RunningServices -contains 'api' -or $RunningServices -contains 'worker') {
            throw 'Reset recusado: API e worker precisam estar parados.'
        }
        Invoke-CobraCompose -ComposeArgs @('up', '-d', '--wait', 'db')
        try {
            $Credential.GetNetworkCredential().Password | & docker compose --project-directory $ProjectRoot --env-file $EnvFile -f $ComposeFile -p pf-gestao-recebiveis run --rm --no-deps -T seed python -m gestao_recebiveis.seed --reset --email $Credential.UserName --confirm-database gestao_recebiveis
            if ($LASTEXITCODE -ne 0) { throw 'Falha no reset. Confira o erro acima.' }
        }
        finally { Start-Application }
    }
}

if ($Action -in @('setup', 'start', 'demo', 'reset')) {
    Write-Host 'Gestão de recebíveis: http://localhost:3101 | API: http://localhost:8101/docs'
    Write-Host 'Demo: operador@example.com e leitor@example.com | senha: Recebiveis!2026'
    Write-Host 'Portas personalizadas: consulte .env.'
}
