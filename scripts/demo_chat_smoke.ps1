[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [double]$HealthWaitSeconds = 60,
    [string]$OutputJson = ".\data\smoke\latest-chat-smoke.json",
    [string]$ComposeFile = "docker-compose.gpu.yml",
    [switch]$SkipOpenApiCheck,
    [switch]$SkipSeed,
    [switch]$NoDockerUp
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:RequiredOpenApiPaths = @(
    "/documents/workspaces/{workspace_id}/upload",
    "/documents/workspaces/{workspace_id}/search",
    "/chat/workspaces/{workspace_id}/sessions",
    "/chat/sessions/{session_id}/messages"
)

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function Test-CommandAvailable([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonExe([string]$RepoRoot) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return "py"
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return "python"
    }
    Fail "Python is not available. Install Python or create .venv first."
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        $parts = $trimmed -split '=', 2
        if ($parts.Count -eq 2) {
            $values[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $values
}

function Test-Health([string]$TargetBaseUrl) {
    try {
        $response = Invoke-RestMethod -Uri ($TargetBaseUrl.TrimEnd('/') + '/health') -TimeoutSec 5
        return $response.status -eq 'ok'
    }
    catch {
        return $false
    }
}

function Test-RequiredOpenApiPaths([string]$TargetBaseUrl) {
    try {
        $payload = Invoke-RestMethod -Uri ($TargetBaseUrl.TrimEnd('/') + '/openapi.json') -TimeoutSec 8
        $paths = @($payload.paths.PSObject.Properties.Name)
        $missing = $script:RequiredOpenApiPaths | Where-Object { $_ -notin $paths }
        return @($missing)
    }
    catch {
        return @("OPENAPI_UNAVAILABLE: $($_.Exception.Message)")
    }
}

function Wait-ForHealth([string]$TargetBaseUrl, [double]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health -TargetBaseUrl $TargetBaseUrl) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Ensure-DirectoryForFile([string]$PathValue) {
    $parent = Split-Path -Parent $PathValue
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

Write-Step "SKP pre-demo chat smoke wrapper"
Write-Host "Repo root: $repoRoot"
Write-Host "Base URL:  $BaseUrl"

if (-not (Test-Path (Join-Path $repoRoot '.env'))) {
    Fail "Missing .env in repo root. Copy .env.example to .env and set the expected values first."
}

if (-not (Test-CommandAvailable 'docker')) {
    Fail "docker is not available on PATH. Start Docker Desktop or install Docker first."
}

$pythonExe = Get-PythonExe -RepoRoot $repoRoot
$dotenv = Read-DotEnv -Path (Join-Path $repoRoot '.env')
$ownerEmail = if ($env:SKP_OWNER_EMAIL) { $env:SKP_OWNER_EMAIL } elseif ($dotenv.ContainsKey('SEED_PLATFORM_OWNER_EMAIL')) { $dotenv['SEED_PLATFORM_OWNER_EMAIL'] } else { 'owner@example.com' }

Write-Step "Checking local prerequisites"
& $pythonExe --version

docker compose version | Out-Null

if (-not $NoDockerUp) {
    Write-Step "Starting Docker stack from $ComposeFile"
    docker compose -f $ComposeFile --env-file .env up -d --build | Out-Null
}
else {
    Write-Step "Skipping docker compose up"
}

if (-not (Wait-ForHealth -TargetBaseUrl $BaseUrl -Seconds $HealthWaitSeconds)) {
    Write-Step "docker compose ps"
    docker compose -f $ComposeFile ps
    Write-Step "api logs (tail 120)"
    docker compose -f $ComposeFile logs api --tail 120
    Fail "Docker API failed to become healthy within $HealthWaitSeconds seconds."
}

if (-not $SkipOpenApiCheck) {
    $missingPaths = @(Test-RequiredOpenApiPaths -TargetBaseUrl $BaseUrl)
    if ($missingPaths.Count -gt 0) {
        Fail "Docker API is up but required routes are missing: $($missingPaths -join ', ')"
    }
}

if (-not $SkipSeed) {
    Write-Step "Seeding platform owner inside api container ($ownerEmail)"
    docker compose -f $ComposeFile exec api runuser -u skp -- python /app/scripts/seed.py
}
else {
    Write-Step "Skipping seed step"
}

Write-Step "Running live e2e chat smoke"
Ensure-DirectoryForFile -PathValue $OutputJson
$resolvedOutputJson = Join-Path $repoRoot $OutputJson
$hostDbUrl = if ($env:SKP_SMOKE_DATABASE_URL) { $env:SKP_SMOKE_DATABASE_URL } elseif ($dotenv.ContainsKey('POSTGRES_PORT')) { "postgresql+psycopg://skp:skp@127.0.0.1:$($dotenv['POSTGRES_PORT'])/skp" } else { "postgresql+psycopg://skp:skp@127.0.0.1:5433/skp" }
$hostRedisUrl = if ($env:SKP_SMOKE_REDIS_URL) { $env:SKP_SMOKE_REDIS_URL } elseif ($dotenv.ContainsKey('REDIS_PORT')) { "redis://127.0.0.1:$($dotenv['REDIS_PORT'])/0" } else { "redis://127.0.0.1:6380/0" }
$hostOllamaUrl = if ($env:SKP_SMOKE_OLLAMA_URL) { $env:SKP_SMOKE_OLLAMA_URL } elseif ($dotenv.ContainsKey('OLLAMA_PORT')) { "http://127.0.0.1:$($dotenv['OLLAMA_PORT'])" } else { "http://127.0.0.1:11434" }

$env:DATABASE_URL = $hostDbUrl
$env:REDIS_URL = $hostRedisUrl
$env:EMBEDDING_OLLAMA_BASE_URL = $hostOllamaUrl
$env:ANSWER_GENERATION_OLLAMA_BASE_URL = $hostOllamaUrl

$smokeArgs = @(
    '.\scripts\e2e_chat_smoke.py',
    '--base-url', $BaseUrl,
    '--owner-email', $ownerEmail,
    '--health-wait-seconds', [string]$HealthWaitSeconds,
    '--output-json', $resolvedOutputJson
)
if ($SkipOpenApiCheck) {
    $smokeArgs += '--skip-openapi-check'
}
& $pythonExe @smokeArgs

Write-Step "Smoke lane completed"
Write-Host "Result artifact: $resolvedOutputJson" -ForegroundColor Green
if (Test-Path $resolvedOutputJson) {
    try {
        $summary = Get-Content $resolvedOutputJson -Raw | ConvertFrom-Json
        Write-Host ("Top hit score: {0}" -f $summary.search_top_hit_score)
        Write-Host ("Hit answer: {0}" -f $summary.hit_answer)
        Write-Host ("No-hit answer: {0}" -f $summary.no_hit_answer)
    }
    catch {
        Write-Warning "Smoke artifact was written but summary parsing failed: $($_.Exception.Message)"
    }
}
