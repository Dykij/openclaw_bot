# 🦅 Blackwell Core WSL Proxy Launch (2026)
# Optimized for pure TypeScript runtime and Blackwell architecture

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "🦅 Blackwell Core: Initiating WSL Engine Proxy" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Host Integrity
# No longer clearing python.exe as we are pure TS/Node.
# (WSL distributive assumed as Ubuntu per user environment)


# 2. Path Mapping
# Resolve Repository Root (Parent of the scripts directory)
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WslPath = wsl -d Ubuntu -e wslpath -u $RepoRoot

Write-Host "📂 Mapping: $RepoRoot -> $WslPath" -ForegroundColor DarkGray
Write-Host "🔄 Switching context to Linux Subsystem... Hold Ctrl+C to stop." -ForegroundColor Cyan
Write-Host ""

# 3. Secure Execution
# Make script executable and launch the canonical WSL starter
wsl -d Ubuntu --cd "$WslPath" -e bash -c "chmod +x scripts/start_wsl.sh 2>/dev/null && ./scripts/start_wsl.sh"
$WslExitCode = $LASTEXITCODE

Write-Host ""
if ($WslExitCode -eq 0) {
    Write-Host "✅ [WSL Engine] Session complete." -ForegroundColor Green
}
else {
    Write-Host "🛑 [WSL Engine] Runtime session terminated (exit code: $WslExitCode)." -ForegroundColor DarkYellow
}
