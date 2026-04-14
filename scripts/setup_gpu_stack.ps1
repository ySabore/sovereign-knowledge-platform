param(
  [string]$ComposeFile = "docker-compose.gpu.yml",
  [string]$EmbeddingModel = "nomic-embed-text",
  [string]$GenerationModel = "llama3.2",
  [int]$ApiWaitSeconds = 360
)

$ErrorActionPreference = "Stop"

function Show-Failure {
  Write-Host "`n--- docker compose ps -a ---" -ForegroundColor Yellow
  docker compose -f $ComposeFile ps -a
  Write-Host "`n--- api logs (last 120 lines) ---" -ForegroundColor Yellow
  docker compose -f $ComposeFile logs api --tail 120 2>$null
}

if (-not (Test-Path ".env")) {
  Write-Host "Missing .env — copy .env.example to .env and set JWT_SECRET and SEED_PLATFORM_OWNER_PASSWORD." -ForegroundColor Red
  exit 1
}

Write-Host "Starting SKP GPU stack from $ComposeFile..."
docker compose -f $ComposeFile --env-file .env up -d --build
if ($LASTEXITCODE -ne 0) {
  Show-Failure
  exit $LASTEXITCODE
}

Write-Host "Waiting for API /health (migrations + uvicorn may take 1–3 min on first boot)..."
$deadline = (Get-Date).AddSeconds($ApiWaitSeconds)
$apiOk = $false
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) {
      $apiOk = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 3
  }
}
if (-not $apiOk) {
  Write-Host "API did not become healthy in time. Check logs below." -ForegroundColor Red
  Show-Failure
  exit 1
}

Write-Host "Waiting for Ollama (localhost:${env:OLLAMA_PORT})..."
$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }
$ollamaOk = $false
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:${ollamaPort}/api/tags" -Method Get -TimeoutSec 5
    $ollamaOk = $true
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
if (-not $ollamaOk) {
  Write-Warning "Ollama did not respond on port $ollamaPort — pull steps may fail. Check: docker compose -f $ComposeFile logs ollama"
}

Write-Host "Pulling Ollama models (embedding + generation)..."
docker compose -f $ComposeFile exec ollama ollama pull $EmbeddingModel
if ($LASTEXITCODE -ne 0) { Show-Failure; exit $LASTEXITCODE }
docker compose -f $ComposeFile exec ollama ollama pull $GenerationModel
if ($LASTEXITCODE -ne 0) { Show-Failure; exit $LASTEXITCODE }

Write-Host "Seeding platform owner (idempotent)..."
docker compose -f $ComposeFile exec api runuser -u skp -- python /app/scripts/seed.py
if ($LASTEXITCODE -ne 0) {
  Show-Failure
  exit $LASTEXITCODE
}

Write-Host "`nDone. Verify:" -ForegroundColor Green
Write-Host "  API:        http://127.0.0.1:8000/health"
Write-Host "  Readiness:  http://127.0.0.1:8000/health/ready"
Write-Host "  AI Ready:   http://127.0.0.1:8000/health/ai"
Write-Host "  Swagger:    http://127.0.0.1:8000/docs"
Write-Host "  Frontend:   cd frontend; npm run dev"
Write-Host "`nSee docs/deploy/GPU_RTX5090.md for troubleshooting."
