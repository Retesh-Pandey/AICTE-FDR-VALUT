# AICTE Smart FDR Portal — Reset Demo Database (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== Resetting AICTE FDR Demo Database ===" -ForegroundColor Cyan
$BackendDir = Join-Path $PSScriptRoot "..\backend"
Set-Location $BackendDir

$PythonBin = Join-Path $BackendDir ".venv\Scripts\python.exe"
$AlembicBin = Join-Path $BackendDir ".venv\Scripts\alembic.exe"

if (-not (Test-Path $PythonBin)) {
    $PythonBin = "python"
    $AlembicBin = "alembic"
}

Write-Host "1. Applying database migrations to head..." -ForegroundColor Yellow
& $AlembicBin upgrade head

Write-Host "2. Seeding clean demo dataset..." -ForegroundColor Yellow
& $PythonBin -m app.db.seed

Write-Host "=== Demo database successfully reset! ===" -ForegroundColor Green
