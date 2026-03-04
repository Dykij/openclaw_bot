$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " OpenClaw v2026: Ollama Setup (AMD RX 6600)" -ForegroundColor Cyan
Write-Host " Полная загрузка 16 уникальных моделей" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 0. Detect Windows IP for WSL connectivity
$WindowsIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1).IPAddress
if (-not $WindowsIP) { $WindowsIP = "192.168.0.212" }
Write-Host "[*] Windows IP для WSL: $WindowsIP" -ForegroundColor Magenta

# 1. Check if Ollama is installed
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "[+] Ollama уже установлен." -ForegroundColor Green
} else {
    Write-Host "[!] Ollama не найден. Скачиваю установщик..." -ForegroundColor Yellow
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installerPath
    Start-Process -FilePath $installerPath -Wait
    Write-Host "[+] Ollama установлен." -ForegroundColor Green
}

# Ensure Ollama is serving (bind to 0.0.0.0 for WSL access)
Write-Host "[!] Запускаю Ollama сервер (0.0.0.0:11434 для WSL)..." -ForegroundColor Yellow
$env:OLLAMA_HOST = "0.0.0.0:11434"
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 5

# 2. Full list of 16 unique models for the Dual-Brigade architecture
# Все модели ≤ 8GB VRAM (AMD RX 6600) с max_concurrent_models=1
$modelsToPull = @(
    # === Бригада Dmarket (10 ролей, 9 уникальных моделей) ===
    "deepseek-r1:8b",        # Planner              | 5.2 GB
    "llama3.1:8b",           # Foreman (общий)      | 4.9 GB
    "qwen2.5-coder:7b",      # Executor_API + Lat.  | 4.7 GB
    "gemma2:9b",             # Executor_Parser      | 5.4 GB
    "codellama:7b",          # Executor_Logic       | 3.8 GB
    "granite-code:8b",       # Auditor (общий)      | 4.6 GB
    "mistral:v0.3",          # Archivist (Dmarket)  | 4.4 GB
    "opencoder:8b",          # Risk_Analyst         | 4.7 GB
    "stable-code:3b",        # Market_Trend_Extr.   | 1.6 GB
    # === Бригада OpenClaw (10 ролей, 7 новых уникальных моделей) ===
    "hermes3",               # Planner (OpenClaw)   | 4.7 GB
    "deepseek-coder:6.7b",   # Executor_Architect   | 3.8 GB
    "qwen2.5:7b",            # Executor_Tools       | 4.7 GB
    "starcoder2",            # Executor_Swarm       | 1.7 GB
    "dolphin-llama3:8b",     # Archivist (OpenClaw) | 4.7 GB
    "yi-coder",              # State_Manager        | 5.0 GB
    "llama3.2",              # Hardware_Optimizer   | 2.0 GB
    "starcoder2:3b"          # Sandbox_Guardian     | 1.7 GB
)

$totalModels = $modelsToPull.Count
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Загрузка $totalModels уникальных моделей (~65GB Total)..." -ForegroundColor Cyan
Write-Host " VRAM-режим: последовательная загрузка (keep_alive=0)" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan

$pulled = 0
$failed = @()

foreach ($model in $modelsToPull) {
    $pulled++
    Write-Host "[$pulled/$totalModels] Загружаю $model..." -ForegroundColor Yellow
    try {
        ollama pull $model
        Write-Host "[+] $model — готова." -ForegroundColor Green
    } catch {
        Write-Host "[-] ОШИБКА: $model — не удалось загрузить." -ForegroundColor Red
        $failed += $model
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host " ✅ Все $totalModels моделей загружены!" -ForegroundColor Green
} else {
    Write-Host " ⚠️  Загружено: $($totalModels - $failed.Count)/$totalModels" -ForegroundColor Yellow
    Write-Host " ❌ Не загружены:" -ForegroundColor Red
    foreach ($f in $failed) { Write-Host "    - $f" -ForegroundColor Red }
}
Write-Host ""
Write-Host " Для WSL-подключения:" -ForegroundColor Cyan
Write-Host "   export OLLAMA_HOST=http://${WindowsIP}:11434" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan
