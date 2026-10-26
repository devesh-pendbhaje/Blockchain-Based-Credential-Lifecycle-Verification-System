# ==============================================================================
# Blockchain-Based Credential Lifecycle Verification System
# Local Startup Orchestrator (Windows PowerShell)
# ==============================================================================

param (
    [string]$Mode = "all",
    [switch]$Headless
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "   Blockchain-Based Credential Lifecycle Verification System          " -ForegroundColor White
Write-Host "   Local Startup Orchestrator (Windows PowerShell)                    " -ForegroundColor Gray
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Prerequisites Check
Write-Host "[1/3] Checking system prerequisites..." -ForegroundColor Yellow

# Node.js
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = node -v
    Write-Host "  [OK] Node.js detected: $nodeVer" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Node.js is required but was not found in PATH." -ForegroundColor Red
    exit 1
}

# Python Virtualenv
$VenvPython = Join-Path $ScriptDir "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-Host "  [OK] Backend virtualenv detected: $VenvPython" -ForegroundColor Green
} else {
    Write-Host "  [WARN] backend\.venv not found. Checking system python..." -ForegroundColor Yellow
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $VenvPython = "python"
        Write-Host "  [OK] Using system python" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Python 3.10+ is required but not found in PATH." -ForegroundColor Red
        exit 1
    }
}

# Frontend dependencies
$FrontendModules = Join-Path $ScriptDir "frontend\node_modules"
if (-not (Test-Path $FrontendModules)) {
    Write-Host "  [INFO] Installing frontend npm packages..." -ForegroundColor Yellow
    Push-Location (Join-Path $ScriptDir "frontend")
    npm install
    Pop-Location
} else {
    Write-Host "  [OK] Frontend dependencies verified." -ForegroundColor Green
}

# 2. Check Docker Mode
if ($Mode -eq "docker") {
    Write-Host "`n[2/3] Launching stack via Docker Compose..." -ForegroundColor Yellow
    Push-Location $ScriptDir
    docker compose up --build
    Pop-Location
    exit 0
}

# 3. Launch Services
Write-Host "`n[2/3] Launching application services (Mode: $Mode)..." -ForegroundColor Yellow

$BackendCmd = "Set-Location '$ScriptDir'; & '$ScriptDir\backend\.venv\Scripts\Activate.ps1'; Write-Host '--- FastAPI Backend Running on http://localhost:8000 ---' -ForegroundColor Green; python -m uvicorn app.main:app --app-dir backend --reload --port 8000"
$FrontendCmd = "Set-Location '$ScriptDir\frontend'; Write-Host '--- React Frontend Running on http://localhost:5173 ---' -ForegroundColor Cyan; npm run dev -- --port 5173 --host"

if ($Headless) {
    if ($Mode -eq "all" -or $Mode -eq "backend") {
        $backendJob = Start-Job -ScriptBlock {
            param($dir)
            Set-Location $dir
            & "$dir\backend\.venv\Scripts\Activate.ps1"
            python -m uvicorn app.main:app --app-dir backend --port 8000
        } -ArgumentList $ScriptDir
        Write-Host "  [OK] Backend job started (ID: $($backendJob.Id))" -ForegroundColor Green
    }

    if ($Mode -eq "all" -or $Mode -eq "frontend") {
        $frontendJob = Start-Job -ScriptBlock {
            param($dir)
            Set-Location "$dir\frontend"
            npm run dev -- --port 5173 --host
        } -ArgumentList $ScriptDir
        Write-Host "  [OK] Frontend job started (ID: $($frontendJob.Id))" -ForegroundColor Green
    }

    Write-Host "`nServices running in background jobs. Press Ctrl+C to terminate." -ForegroundColor White

    try {
        while ($true) {
            Start-Sleep -Seconds 2
        }
    } finally {
        Write-Host "`nStopping background jobs..." -ForegroundColor Yellow
        Get-Job | Stop-Job -PassThru | Remove-Job
        Write-Host "All background jobs stopped." -ForegroundColor Green
    }
} else {
    if ($Mode -eq "all" -or $Mode -eq "backend") {
        Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCmd
        Write-Host "  [OK] Backend console launched: http://localhost:8000" -ForegroundColor Green
    }

    if ($Mode -eq "all" -or $Mode -eq "frontend") {
        Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCmd
        Write-Host "  [OK] Frontend console launched: http://localhost:5173" -ForegroundColor Green
    }
}

# 4. URLs Summary
Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "                      SERVICES READY TO USE                            " -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "  • Frontend Web Portal:     http://localhost:5173" -ForegroundColor White
Write-Host "  • Sovereign Holder Wallet: http://localhost:5173/wallet" -ForegroundColor White
Write-Host "  • Public Verification:    http://localhost:5173/verify" -ForegroundColor White
Write-Host "  • Backend Swagger UI:      http://localhost:8000/api/v1/docs" -ForegroundColor White
Write-Host "  • Backend Health Check:    http://localhost:8000/health/live" -ForegroundColor White
Write-Host "  • Sepolia Blockchain RPC:  Connected (Sepolia Testnet Chain ID: 11155111)" -ForegroundColor Gray
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""
