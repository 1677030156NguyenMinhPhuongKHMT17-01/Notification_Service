<#
.SYNOPSIS
    5-minute reproducible Demo Pack runner for FIT4110 Lab 06 Plug-a-thon
    (Notification Service - Group 7, Pair 04: Core Business -> Notification).

.DESCRIPTION
    Executes the full end-to-end verification sequence from a clean clone:
      1. Verifies byte-for-byte SHA-256 parity of frozen v1.0.0 contracts.
      2. Lints OpenAPI 3.1 contract (Spectral) and validates Compose overlays.
      3. Creates a temporary .env from .env.example (removed automatically on exit).
      4. Starts the 3-container Compose stack (api + db + mqtt-broker) with --wait.
      5. Verifies non-root runtime user (uid=10001), /health, and /ready.
      6. Runs Pair-04 MQTT handshake, fault injection (DLQ/Q09/401/409/422), and /retry recovery.
      7. Runs the 21-request Newman Plug-a-thon test suite and emits HTML/XML reports.

.PARAMETER Clean
    Tear down containers and volumes (`docker compose down -v`) when finished.

.PARAMETER SkipBuild
    Skip `--build` when starting Compose (useful when image is already built).

.PARAMETER SkipNewman
    Skip installing npm packages / running the Newman test suite.

.PARAMETER NoDlqRecovery
    Skip the `--with-compose-dlq-recovery` transient failure + manual retry phase.

.PARAMETER Port
    Override host port mapped to API container port 8000 (default: from .env.example, 8000).
#>
[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$SkipBuild,
    [switch]$SkipNewman,
    [switch]$NoDlqRecovery,
    [int]$Port = 0,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help -Detailed $MyInvocation.MyCommand.Path
    exit 0
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Lab06Dir = Join-Path $RepoRoot "06_Plugathon"
$EnvExamplePath = Join-Path $Lab06Dir ".env.example"
$EnvPath = Join-Path $Lab06Dir ".env"
$ReportsDir = Join-Path $Lab06Dir "reports"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }
    foreach ($rawLine in (Get-Content -Path $Path -Encoding UTF8)) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $values[$key] = $val
    }
    return $values
}

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $Lab06Dir
    )
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed (exit=$LASTEXITCODE): $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

Assert-Command "docker"
Assert-Command "python"
if (-not $SkipNewman) {
    Assert-Command "npm"
}

$dockerCheck = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not running or inaccessible. Start Docker Desktop first.`n$dockerCheck"
}

$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$CreatedTempEnv = $false
$PrevAppPort = $env:APP_PORT
$PrevAuthToken = $env:AUTH_TOKEN
$PrevDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE

try {
    $env:PYTHONDONTWRITEBYTECODE = "1"

    if (-not (Test-Path $EnvPath)) {
        Copy-Item -Path $EnvExamplePath -Destination $EnvPath
        $CreatedTempEnv = $true
        Write-Host "[INFO] Created temporary 06_Plugathon/.env from .env.example (will be cleaned up on exit)."
    }
    else {
        Write-Host "[INFO] Using existing 06_Plugathon/.env (will be preserved on exit)."
    }

    $cfg = Read-DotEnv -Path $EnvPath
    $AppPort = if ($Port -gt 0) { $Port } elseif ($cfg.ContainsKey("APP_PORT") -and $cfg["APP_PORT"]) { [int]$cfg["APP_PORT"] } else { 8000 }
    $MqttPort = if ($cfg.ContainsKey("MQTT_PORT") -and $cfg["MQTT_PORT"]) { [int]$cfg["MQTT_PORT"] } else { 1883 }
    $AuthToken = if ($cfg.ContainsKey("AUTH_TOKEN") -and $cfg["AUTH_TOKEN"]) { $cfg["AUTH_TOKEN"] } else { "plugathon-dev-token" }

    $env:APP_PORT = "$AppPort"
    $env:AUTH_TOKEN = $AuthToken
    $BaseUrl = "http://127.0.0.1:$AppPort"
    $BrokerUrl = "mqtt://127.0.0.1:$MqttPort"

    Write-Step "1/6 Verifying frozen v1.0.0 contracts (SHA-256 parity)"
    Invoke-Native -FilePath "python" -Arguments @("scripts/verify_frozen_contracts.py")

    Write-Step "2/6 Validating Compose configs (standalone + external class-net overlay)"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "config", "--quiet")
    Invoke-Native -FilePath "docker" -Arguments @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.external-broker.yml", "config", "--quiet")
    Write-Host "[PASS] Both standalone and external-broker Compose configurations are valid."

    if (-not $SkipNewman) {
        Write-Step "3/6 Ensuring Node tooling (Spectral + Newman) & linting OpenAPI 3.1 contract"
        if (-not (Test-Path (Join-Path $Lab06Dir "node_modules"))) {
            Invoke-Native -FilePath "npm" -Arguments @("ci")
        }
        Invoke-Native -FilePath "npm" -Arguments @("run", "lint:openapi")
    }
    else {
        Write-Step "3/6 Skipping npm/OpenAPI lint (-SkipNewman specified)"
    }

    Write-Step "4/6 Starting 3-container Plug-a-thon stack (api + db + mqtt-broker)"
    $upArgs = @("compose", "up", "-d")
    if (-not $SkipBuild) {
        $upArgs += "--build"
    }
    $upArgs += "--wait"
    Invoke-Native -FilePath "docker" -Arguments $upArgs
    Invoke-Native -FilePath "docker" -Arguments @("compose", "ps")

    Push-Location $Lab06Dir
    try {
        $idOut = (& docker compose exec -T api id) -join " "
        if ($LASTEXITCODE -ne 0 -or $idOut -notmatch "uid=10001\(appuser\)") {
            throw "Expected non-root uid=10001(appuser), got: $idOut"
        }
        Write-Host "[PASS] API container user verified: $idOut"
    }
    finally {
        Pop-Location
    }

    Write-Step "5/6 Verifying /health and /ready endpoints"
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 5
    if ($health.status -ne "ok") {
        throw "Unexpected /health payload: $($health | ConvertTo-Json -Compress)"
    }
    Write-Host "GET $BaseUrl/health ->"
    Write-Host ($health | ConvertTo-Json -Depth 5)

    $ready = Invoke-RestMethod -Uri "$BaseUrl/ready" -Method Get -TimeoutSec 5
    if ($ready.status -ne "ready" -or -not $ready.dependencies.database.ready -or -not $ready.dependencies.mqtt.connected) {
        throw "Unexpected /ready payload: $($ready | ConvertTo-Json -Compress)"
    }
    Write-Host "GET $BaseUrl/ready ->"
    Write-Host ($ready | ConvertTo-Json -Depth 5)

    Write-Step "6/6 Running Pair-04 E2E handshake, fault/DLQ injection & Newman verification"
    $e2eArgs = @(
        "scripts/run_plugathon_e2e.py",
        "--base-url", $BaseUrl,
        "--broker", $BrokerUrl
    )
    if (-not $NoDlqRecovery) {
        $e2eArgs += "--with-compose-dlq-recovery"
    }
    Invoke-Native -FilePath "python" -Arguments $e2eArgs

    if (-not $SkipNewman) {
        if (-not (Test-Path $ReportsDir)) {
            New-Item -ItemType Directory -Path $ReportsDir -Force | Out-Null
        }
        if ($AppPort -eq 8000 -and $AuthToken -eq "plugathon-dev-token") {
            Invoke-Native -FilePath "npm" -Arguments @("run", "test:plugathon")
        }
        else {
            Invoke-Native -FilePath "npm" -Arguments @(
                "run", "test:plugathon", "--",
                "--env-var", "baseUrl=http://localhost:$AppPort",
                "--env-var", "authToken=$AuthToken"
            )
        }
    }

    $Stopwatch.Stop()
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " FIT4110 Lab 06 Demo Pack — ALL CHECKS PASSED" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host (" Elapsed time : {0:N1}s (target <= 300s)" -f $Stopwatch.Elapsed.TotalSeconds)
    Write-Host " Demo UI      : $BaseUrl/"
    Write-Host " Swagger UI   : $BaseUrl/docs"
    Write-Host " Health/Ready : $BaseUrl/health | $BaseUrl/ready"
    if (-not $SkipNewman) {
        Write-Host " Newman HTML  : 06_Plugathon/reports/newman-plugathon.html"
        Write-Host " Newman XML   : 06_Plugathon/reports/newman-plugathon.xml"
    }
    if ($Clean) {
        Write-Host " Cleanup mode : -Clean enabled (stack will be torn down now)"
    }
    else {
        Write-Host " Cleanup cmd  : docker compose -f 06_Plugathon/docker-compose.yml down -v"
    }
    Write-Host "============================================================" -ForegroundColor Green
}
finally {
    if ($Clean) {
        Write-Step "Cleaning up Compose stack (-Clean specified)"
        Push-Location $Lab06Dir
        try {
            & docker compose down -v
        }
        finally {
            Pop-Location
        }
    }

    if ($CreatedTempEnv -and (Test-Path $EnvPath)) {
        Remove-Item -Path $EnvPath -Force
        Write-Host "[INFO] Removed temporary 06_Plugathon/.env."
    }

    $env:APP_PORT = $PrevAppPort
    $env:AUTH_TOKEN = $PrevAuthToken
    $env:PYTHONDONTWRITEBYTECODE = $PrevDontWriteBytecode
}
