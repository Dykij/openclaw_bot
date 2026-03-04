# Powershell Скрипт для мгновенного запуска OpenClaw Bot через WSL

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 Инициализация загрузки WSL для OpenClaw" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Проверяем и убиваем другие запущенные экземпляры в Windows (при переходе с нативного запуска на WSL)
$processes = Get-Process -Name python -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "⚠️ Найдено $($processes.Count) процессов python.exe. Очистка для предотвращения конфликта..." -ForegroundColor Yellow
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Старые процессы очищены." -ForegroundColor Green
}

# Текущая директория бота
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Конвертация Windows пути (D:\openclaw...) в путь WSL (/mnt/d/openclaw...) 
# wslpath работает прямо из powershell
$WslPath = wsl -d Ubuntu -e wslpath -u $ScriptDir

Write-Host "📂 Рабочая директория (WSL): $WslPath" -ForegroundColor DarkGray
Write-Host "🔄 Передача управления в подсистему Linux... Нажмите Ctrl+C для выхода." -ForegroundColor Cyan
Write-Host ""

# Делаем скрипт исполняемым и запускаем его напрямую в Ubuntu/WSL
wsl -d Ubuntu --cd "$WslPath" -e bash -c "chmod +x start_wsl.sh && ./start_wsl.sh"

Write-Host ""
Write-Host "🛑 Работа WSL скрипта завершена." -ForegroundColor Red
