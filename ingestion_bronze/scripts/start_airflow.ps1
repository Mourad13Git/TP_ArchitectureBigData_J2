# Demarre Airflow (Docker) — UI http://localhost:8081  login: admin / admin
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Demarrage Airflow (postgres + webserver + scheduler)..."
docker compose -f docker-compose.airflow.yml up -d

Write-Host ""
Write-Host "Attente du webserver (30-90 s)..."
Start-Sleep -Seconds 45

try {
    $r = Invoke-WebRequest -Uri "http://localhost:8081/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "Airflow OK - http://localhost:8081"
    Write-Host "Login: admin / admin"
    Write-Host "DAG: bce_ingestion_bronze_kbo"
} catch {
    Write-Host "Webserver encore en cours de demarrage. Ouvrez http://localhost:8081 dans 1-2 min."
    Write-Host "Logs: docker compose -f docker-compose.airflow.yml logs -f airflow-webserver"
}
