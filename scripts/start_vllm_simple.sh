#!/bin/bash
# Start vLLM server in WSL for OpenClaw bot (simple, no speculative decoding)
set -euo pipefail

export HF_HOME=/mnt/d/vllm_models
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
VENV_PYTHON=/mnt/d/vllm_env/bin/python3
MODEL="${1:-Qwen/Qwen2.5-Coder-14B-Instruct-AWQ}"
PORT=8000
GPU_UTIL=0.92
MAX_MODEL_LEN=8192

echo "Starting vLLM: $MODEL on port $PORT"

exec $VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host 0.0.0.0 \
    --port $PORT \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_UTIL \
    --dtype auto \
    --trust-remote-code \
    --enable-prefix-caching \
    --enforce-eager
