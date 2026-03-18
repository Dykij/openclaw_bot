#!/bin/bash
# Download all AWQ models for vLLM to /mnt/d/vllm_models
export HF_HOME=/mnt/d/vllm_models

VENV=/mnt/d/vllm_env/bin/python3

echo "=== Downloading AWQ models to $HF_HOME ==="

echo "[1/4] hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
$VENV -c "from huggingface_hub import snapshot_download; snapshot_download('hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4')"

echo "[2/4] casperhansen/deepseek-r1-distill-llama-8b-awq"
$VENV -c "from huggingface_hub import snapshot_download; snapshot_download('casperhansen/deepseek-r1-distill-llama-8b-awq')"

echo "[3/4] Qwen/Qwen2.5-Coder-7B-Instruct-AWQ"
$VENV -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-Coder-7B-Instruct-AWQ')"

echo "[4/4] pytorch/gemma-3-12b-it-AWQ-INT4"
$VENV -c "from huggingface_hub import snapshot_download; snapshot_download('pytorch/gemma-3-12b-it-AWQ-INT4')"

echo "=== All models downloaded ==="
ls -lh $HF_HOME/hub/models--*/
