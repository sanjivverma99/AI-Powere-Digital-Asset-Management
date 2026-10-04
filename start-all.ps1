# Start all DAM services locally (no Docker required)
$root = $PSScriptRoot

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Starting AI-Powered DAM Native Services        " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# MongoDB is configured through MONGODB_URL in .env or .env.local.

# 1. Qdrant
$qdrantDir = Join-Path $root "infra\qdrant"
$qdrantExe = Join-Path $qdrantDir "qdrant.exe"
if (Test-Path $qdrantExe) {
    try {
        Invoke-RestMethod -Uri "http://localhost:6333/readyz" -TimeoutSec 1 -ErrorAction Stop | Out-Null
        Write-Host "[1/3] Qdrant is already running." -ForegroundColor Green
    } catch {
        Write-Host "[1/3] Starting Qdrant..." -ForegroundColor Yellow
        Start-Process $qdrantExe -WorkingDirectory $qdrantDir -WindowStyle Minimized
        Start-Sleep -Seconds 2
    }
}

# 2. Backend (FastAPI / Uvicorn)
try {
    Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 1 -ErrorAction Stop | Out-Null
    Write-Host "[2/3] Backend is already running." -ForegroundColor Green
} catch {
    Write-Host "[2/3] Starting Backend on http://localhost:8000..." -ForegroundColor Yellow
    Start-Process python -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--app-dir", $root, "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $root -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

# 3. Frontend (Vite)
try {
    Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop | Out-Null
    Write-Host "[3/3] Frontend is already running on http://localhost:5173." -ForegroundColor Green
} catch {
    Write-Host "[3/3] Starting Frontend on http://localhost:5173..." -ForegroundColor Yellow
    $frontendDir = Join-Path $root "frontend"
    Start-Process npm -ArgumentList "run", "dev" -WorkingDirectory $frontendDir -WindowStyle Minimized
}

Write-Host ""
Write-Host "All services active:" -ForegroundColor Green
Write-Host "  • Frontend:   http://localhost:5173" -ForegroundColor White
Write-Host "  • Backend:    http://localhost:8000 (Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host "  • Qdrant:     http://localhost:6333" -ForegroundColor White
Write-Host "  • MongoDB:    configured via MONGODB_URL" -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
