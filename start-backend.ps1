# ── Start FastAPI backend (local, no Docker) ──────────────────
$root = $PSScriptRoot
Set-Location $root

# Load local MongoDB, Qdrant, and Ollama configuration.
$env_file = Join-Path $root ".env.local"
if (Test-Path $env_file) {
    Get-Content $env_file | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
        }
    }
    Write-Host "[Backend] Loaded env from .env.local" -ForegroundColor Green
}

Write-Host "[Backend] Starting uvicorn on http://localhost:8000" -ForegroundColor Cyan
python -m uvicorn backend.app.main:app --app-dir $root --host 0.0.0.0 --port 8000 --reload
