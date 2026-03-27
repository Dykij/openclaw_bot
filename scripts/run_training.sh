#!/usr/bin/env bash
set -e
source /mnt/d/vllm_env/bin/activate
echo "=== Starting training $(date) ==="
python /mnt/d/openclaw_bot/openclaw_bot/scripts/train_lora.py \
  --dataset /mnt/d/openclaw_bot/openclaw_bot/data/training/raw_dialogues.jsonl \
  --model unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit \
  --adapter-name openclaw-7b-v1 \
  --lora-rank 64 \
  --lora-alpha 128 \
  --dropout 0 \
  --epochs 15 \
  --lr 2e-4 \
  --warmup-ratio 0.05 \
  --weight-decay 0 \
  --max-seq-len 512 \
  --grad-accum 4 \
  --val-split 0 \
  --wandb-project ""
RC=$?
echo "=== Training finished $(date) EXIT_CODE=$RC ==="
