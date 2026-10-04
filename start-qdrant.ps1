# ── Start Qdrant (local, no Docker) ──────────────────────────
$root = $PSScriptRoot
$qdrantDir = Join-Path $root "infra\qdrant"
$exe = Join-Path $qdrantDir "qdrant.exe"

if (-not (Test-Path $exe)) {
    Write-Host "[ERROR] qdrant.exe not found at $exe" -ForegroundColor Red
    exit 1
}

Write-Host "[Qdrant] Starting on http://localhost:6333..." -ForegroundColor Cyan
Set-Location $qdrantDir
& $exe
