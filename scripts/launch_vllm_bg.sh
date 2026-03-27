#!/bin/bash
# Wrapper to start vLLM in background
nohup bash /mnt/d/openclaw_bot/openclaw_bot/scripts/start_vllm_simple.sh > /tmp/vllm_simple.log 2>&1 &
echo "vLLM PID: $!"
