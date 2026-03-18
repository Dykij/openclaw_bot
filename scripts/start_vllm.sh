#!/bin/bash
# Start vLLM server in WSL for OpenClaw bot
# Usage: bash /mnt/d/openclaw_bot/openclaw_bot/scripts/start_vllm.sh [model_name]

export HF_HOME=/mnt/d/vllm_models
VENV_PYTHON=/mnt/d/vllm_env/bin/python3
MODEL="${1:-hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4}"
PORT=8000

echo "Starting vLLM server..."
echo "  Model: $MODEL"
echo "  Port: $PORT"
echo "  HF_HOME: $HF_HOME"

exec $VENV_PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host 0.0.0.0 \
    --port $PORT \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --quantization awq_marlin \
    --dtype auto \
    --trust-remote-code
