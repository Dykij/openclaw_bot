#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

echo -ne "\033]0;OpenClaw WSL Gateway\007"

WIN_HOST_IP="$(ip route show default 2>/dev/null | awk 'NR==1 { print $3 }')"
export OLLAMA_HOST="http://${WIN_HOST_IP:-127.0.0.1}:11434"
export WSL_ENV="1"
export OPENCLAW_KEEP_ALIVE="0"
export OPENCLAW_FORCE_BUILD="0"
export OPENCLAW_RUNNER_LOG="1"
export OPENCLAW_CONFIG_PATH="${REPO_ROOT}/config/openclaw.json"

echo "Checking Ollama connectivity (${OLLAMA_HOST})..."
if ! curl -Is --connect-timeout 2 "${OLLAMA_HOST}" > /dev/null; then
    echo "WARNING: Ollama is unreachable at ${OLLAMA_HOST}."
    echo "Make sure Ollama is running on the Windows host and bound to 0.0.0.0."
    echo "Continuing anyway, as discovery might happen later..."
fi

echo "===================================================="
echo "OpenClaw: WSL gateway launcher"
echo "Repo root: ${REPO_ROOT}"
echo "Config: ${OPENCLAW_CONFIG_PATH}"
echo "Windows host: ${WIN_HOST_IP:-unknown}"
echo "===================================================="

cd "${REPO_ROOT}"

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: node is not installed in WSL. Install Node 22+ inside Ubuntu."
    exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
    echo "ERROR: pnpm is not installed in WSL. Install pnpm inside Ubuntu."
    exit 1
fi

if [ ! -f "${OPENCLAW_CONFIG_PATH}" ]; then
    echo "ERROR: config file not found at ${OPENCLAW_CONFIG_PATH}"
    exit 1
fi

if [ ! -f "dist/entry.js" ]; then
    echo "Build output missing. Running pnpm build..."
    pnpm build
fi

if ! node -e "const fs=require('node:fs'); const cfg=JSON.parse(fs.readFileSync(process.env.OPENCLAW_CONFIG_PATH,'utf8')); process.exit(cfg?.gateway?.mode === 'local' ? 0 : 1)"; then
    echo "gateway.mode is not set to local. Updating config..."
    node openclaw.mjs config set gateway.mode local
fi

# Check if gateway is already running before attempting to start
if node openclaw.mjs gateway status --timeout 3000 > /dev/null 2>&1; then
    echo ""
    echo "✅ OpenClaw gateway is already running."
    node openclaw.mjs gateway status --timeout 2000 2>/dev/null || true
    echo ""
    echo "   To stop:    OPENCLAW_CONFIG_PATH=${OPENCLAW_CONFIG_PATH} node openclaw.mjs gateway stop"
    echo "   To restart: OPENCLAW_CONFIG_PATH=${OPENCLAW_CONFIG_PATH} node openclaw.mjs gateway stop && ./scripts/start_wsl.sh"
    exit 0
fi

echo "Launching OpenClaw gateway..."
exec node openclaw.mjs gateway run
