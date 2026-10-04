# Start the local MongoDB service defined in docker-compose.yml.
$root = $PSScriptRoot
Push-Location $root

try {
    docker compose up -d mongo
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to start MongoDB with Docker Compose."
    }

    Write-Host "[MongoDB] Local MongoDB is ready." -ForegroundColor Green
} finally {
    Pop-Location
}
