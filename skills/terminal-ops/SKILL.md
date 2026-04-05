---
name: terminal-ops
description: "Terminal mastery: shell scripting (Bash/PowerShell/Zsh), process management, system diagnostics, Docker ops, SSH tunnels. Use when: writing scripts, debugging processes, managing containers, automating system tasks."
version: 1.0.0
---

# Terminal Operations

## Purpose

Expert terminal usage: shell scripting, process management, Docker, system diagnostics.

## PowerShell (Primary for Windows hosts)

### Idiomatic Patterns

```powershell
# Pipeline processing
Get-ChildItem -Recurse -Filter "*.ts" |
    Where-Object { $_.Length -gt 10KB } |
    Sort-Object Length -Descending |
    Select-Object Name, @{N='SizeKB';E={[math]::Round($_.Length/1KB,1)}} -First 10

# Error handling
try {
    $result = Invoke-RestMethod -Uri $url -Method Post -Body $json -ContentType 'application/json'
} catch [System.Net.WebException] {
    Write-Error "Network error: $_"
} catch {
    Write-Error "Unexpected: $_"
}

# Parallel execution (PowerShell 7+)
1..10 | ForEach-Object -Parallel {
    Invoke-RestMethod "https://api.example.com/items/$_"
} -ThrottleLimit 4
```

### System Diagnostics

```powershell
# Process by CPU
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, WorkingSet64

# Port usage
Get-NetTCPConnection -State Listen | Select-Object LocalPort, OwningProcess |
    ForEach-Object { $p = Get-Process -Id $_.OwningProcess; [PSCustomObject]@{Port=$_.LocalPort;Process=$p.Name} }

# Disk space
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}
```

## Bash (Linux/macOS/WSL)

### Shell Script Template

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/tmp/$(basename "$0" .sh).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "FATAL: $*"; exit 1; }

main() {
    log "Starting..."
    # Your logic here
    log "Done."
}

main "$@"
```

### Process Management

```bash
# Find process by port
lsof -i :8080 -t | xargs kill -9

# Background with nohup
nohup ./server --port 8080 > /tmp/server.log 2>&1 &
echo $! > /tmp/server.pid

# Monitor logs
tail -f /tmp/server.log | grep --line-buffered "ERROR"
```

## Docker Operations

```bash
# Build with cache optimization
docker build --target production -t app:latest .

# Compose operations
docker compose up -d --build
docker compose logs -f --tail=100 app
docker compose exec app sh

# Cleanup
docker system prune -af --volumes  # WARNING: destructive

# Health check
docker inspect --format='{{.State.Health.Status}}' container_name
```

## SSH Tunnels & Remote

```bash
# Local port forward (access remote DB locally)
ssh -L 5432:localhost:5432 user@remote-host

# Remote port forward (expose local to remote)
ssh -R 8080:localhost:3000 user@remote-host

# SOCKS proxy
ssh -D 1080 user@remote-host

# Persistent session with tmux
ssh user@host -t 'tmux new -A -s main'
```

## Rules

1. **Always use `set -euo pipefail`** in bash scripts
2. **Always quote variables**: `"$var"` not `$var`
3. **Check command existence**: `command -v jq >/dev/null || die "jq required"`
4. **Use `shellcheck`** on all bash scripts
5. **Log all destructive operations** before executing
6. **Use `--dry-run`** flags when available for first pass
