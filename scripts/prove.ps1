[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProofRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ProofCompose = Join-Path $ProofRoot 'compose.proof.yaml'
if ((Get-Content -LiteralPath $ProofCompose -Raw) -notmatch '(?m)^name: pf-gestao-recebiveis-proof\s*$') {
    throw 'Prova recusada: Compose precisa identificar pf-gestao-recebiveis-proof.'
}
$RunId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$EvidenceDirectory = Join-Path $ProofRoot "artifacts/proof/$RunId"
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$PreviousEvidence = $env:CF_PROOF_EVIDENCE_DIR
$env:CF_PROOF_EVIDENCE_DIR = $EvidenceDirectory.Replace('\', '/')
$Commands = [System.Collections.Generic.List[object]]::new()
$Failure = $null
$Started = [DateTime]::UtcNow
$ComposePrefix = @('compose', '--project-directory', $ProofRoot, '-f', $ProofCompose, '-p', 'pf-gestao-recebiveis-proof')

function Invoke-ProofCommand {
    param([string]$Name, [string[]]$DockerArgs, [int]$ExpectedExit = 0)
    $StepStart = [DateTime]::UtcNow
    $LogPath = Join-Path $EvidenceDirectory "$Name.txt"
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker @DockerArgs 2>&1 | Tee-Object -FilePath $LogPath | Write-Host
        $Code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $PreviousPreference }
    $Commands.Add([pscustomobject]@{
        name = $Name; command = 'docker ' + ($DockerArgs -join ' ')
        started_at_utc = $StepStart.ToString('o'); elapsed_seconds = ([DateTime]::UtcNow - $StepStart).TotalSeconds
        exit_code = $Code; expected_exit_code = $ExpectedExit; passed = ($Code -eq $ExpectedExit)
        output = "$Name.txt"
    })
    if ($Code -ne $ExpectedExit) { throw "Etapa $Name falhou: código $Code; esperado $ExpectedExit." }
}

try {
    Invoke-ProofCommand 'concurrent-services' @('ps', '--format', '{{.Names}} {{.Status}} {{.Ports}}')
    Invoke-ProofCommand 'docker-version' @('version', '--format', '{{json .Server}}')
    Invoke-ProofCommand 'compose-version' @('compose', 'version')
    foreach ($BuildService in @('db', 'api', 'frontend', 'e2e')) {
        Invoke-ProofCommand "$BuildService-build" @('compose', '--project-directory', $ProofRoot, '-f', (Join-Path $ProofRoot 'compose.yaml'), '--profile', 'test', 'build', $BuildService)
    }
    Invoke-ProofCommand 'runtime-images' @('image', 'inspect', '--format', '{{.RepoTags}} {{.Id}}', 'gestao-recebiveis-database:local', 'gestao-recebiveis-backend:local', 'gestao-recebiveis-frontend:local', 'gestao-recebiveis-e2e:local')
    Invoke-ProofCommand 'fresh-proof' ($ComposePrefix + @('down', '--volumes', '--remove-orphans'))
    Invoke-ProofCommand 'database-ready' ($ComposePrefix + @('up', '-d', '--wait', '--wait-timeout', '120', 'db'))
    Invoke-ProofCommand 'backend-checks' ($ComposePrefix + @('run', '--rm', '--no-deps', '-e', 'LEASE_SECONDS=60', '-e', 'HEARTBEAT_SECONDS=20', 'probe', 'sh', '/scripts/check-backend.sh'))
    Invoke-ProofCommand 'wrong-mode-rejected' ($ComposePrefix + @('run', '--rm', '--no-deps', '-e', 'CF_PROOF_MODE=denied', 'probe', 'python', 'tests/persistence_probe.py', 'prepare')) 1
    Invoke-ProofCommand 'accepted-process-interrupted' ($ComposePrefix + @('run', '--rm', '--no-deps', 'probe', 'python', 'tests/persistence_probe.py', 'prepare')) 86
    Invoke-ProofCommand 'restart-disposable-database' ($ComposePrefix + @('restart', 'db'))
    Invoke-ProofCommand 'restarted-database-ready' ($ComposePrefix + @('up', '-d', '--wait', '--wait-timeout', '120', 'db'))
    Invoke-ProofCommand 'recover-persisted-acceptance' ($ComposePrefix + @('run', '--rm', '--no-deps', 'probe', 'python', 'tests/persistence_probe.py', 'verify'))
    Invoke-ProofCommand 'fresh-journey' ($ComposePrefix + @('down', '--volumes', '--remove-orphans'))
    Invoke-ProofCommand 'journey-database-ready' ($ComposePrefix + @('up', '-d', '--wait', '--wait-timeout', '120', 'db'))
    Invoke-ProofCommand 'journey-migrate' ($ComposePrefix + @('run', '--rm', '--no-deps', 'probe', 'alembic', 'upgrade', 'head'))
    Invoke-ProofCommand 'journey-seed' ($ComposePrefix + @('run', '--rm', '--no-deps', 'probe', 'python', '-m', 'gestao_recebiveis.seed'))
    Invoke-ProofCommand 'journey-application-ready' ($ComposePrefix + @('up', '-d', '--wait', '--wait-timeout', '120', 'api', 'worker', 'frontend'))
    Invoke-ProofCommand 'proxy-journey' ($ComposePrefix + @('run', '--rm', '--no-deps', 'probe', 'python', 'tests/demo_probe.py'))
    Invoke-ProofCommand 'browser-journey' ($ComposePrefix + @('run', '--rm', '--no-deps', 'e2e'))
}
catch { $Failure = $_.Exception.Message }
finally {
    try { Invoke-ProofCommand 'cleanup-own-proof' ($ComposePrefix + @('down', '--volumes', '--remove-orphans')) }
    catch { if (-not $Failure) { $Failure = $_.Exception.Message } }
    $SourceFiles = @()
    foreach ($Directory in @('backend/src', 'backend/tests', 'backend/migrations', 'frontend/src', 'frontend/tests', 'scripts')) {
        $SourceFiles += Get-ChildItem -LiteralPath (Join-Path $ProofRoot $Directory) -File -Recurse |
            Where-Object { $_.Extension -in @('.py', '.ts', '.tsx', '.css', '.cjs', '.ps1', '.sh') }
    }
    foreach ($Relative in @('compose.yaml', 'compose.proof.yaml', 'database/Dockerfile', 'backend/uv.lock', 'backend/pyproject.toml', 'backend/Dockerfile', 'frontend/package-lock.json', 'frontend/Dockerfile', 'frontend/Dockerfile.e2e', 'data/fixtures/manual.csv')) {
        $SourceFiles += Get-Item -LiteralPath (Join-Path $ProofRoot $Relative)
    }
    $Fingerprints = @($SourceFiles | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{ path = $_.FullName.Substring($ProofRoot.Length + 1).Replace('\', '/'); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() }
    })
    $Fingerprints | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'source-fingerprints.json') -Encoding utf8
    $GitState = & git -C $ProofRoot status --short
    $GitState | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'git-status.txt') -Encoding utf8
    $Report = [pscustomobject]@{
        run_id = $RunId; started_at_utc = $Started.ToString('o'); ended_at_utc = [DateTime]::UtcNow.ToString('o')
        result = $(if ($Failure) { 'failed' } else { 'passed' }); failure = $Failure
        environment = 'Windows host / Docker Linux / pf-gestao-recebiveis-proof / no host ports'
        dataset = 'manual 31-cent acceptance; seed v1/42/2026-08-17; sample CSVs; pytest fixtures'
        code_revision = 'working tree; consult git-status and source-fingerprints'
        executed_steps = $Commands.Count; approved_steps = @($Commands | Where-Object passed).Count
        failed_steps = @($Commands | Where-Object { -not $_.passed }).Count
        commands = $Commands.ToArray()
        limits = @('Local persistent fake provider; no external recipient', 'Process interruption and PostgreSQL restart, not host/disc disaster')
    }
    $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'report.json') -Encoding utf8
    $env:CF_PROOF_EVIDENCE_DIR = $PreviousEvidence
    Write-Host "Evidências: $EvidenceDirectory"
}
if ($Failure) { throw $Failure }
