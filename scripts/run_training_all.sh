#!/usr/bin/env bash
set -e
source /mnt/d/vllm_env/bin/activate
SCRIPTS=/mnt/d/openclaw_bot/openclaw_bot/scripts
DATASET=/mnt/d/openclaw_bot/openclaw_bot/data/training/raw_dialogues.jsonl
LOGS=/mnt/d/openclaw_bot/openclaw_bot/logs

# ═══════════════════════════════════════════════════════════════
# PHASE 1: Qwen2.5-Coder-14B QLoRA
# ═══════════════════════════════════════════════════════════════
echo "=== [1/2] Starting 14B training $(date) ==="
python "$SCRIPTS/train_lora.py" \
  --dataset "$DATASET" \
  --model unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit \
  --adapter-name openclaw-14b-v1 \
  --lora-rank 32 \
  --lora-alpha 64 \
  --dropout 0 \
  --epochs 15 \
  --lr 2e-4 \
  --warmup-ratio 0.05 \
  --weight-decay 0 \
  --max-seq-len 512 \
  --batch-size 1 \
  --grad-accum 16 \
  --val-split 0 \
  --wandb-project ""
echo "=== [1/2] 14B training finished $(date) ==="

# Evaluate 14B
echo "=== [1/2] Evaluating 14B adapter ==="
PYTHONUNBUFFERED=1 python "$SCRIPTS/eval_lora.py" \
  --adapter /mnt/d/lora_adapters/openclaw-14b-v1 \
  --test "$DATASET" \
  --samples 20 \
  --max-new-tokens 256

# ═══════════════════════════════════════════════════════════════
# PHASE 2: DeepSeek-R1-Distill-Qwen-14B QLoRA
# ═══════════════════════════════════════════════════════════════
echo ""
echo "=== [2/2] Starting DeepSeek-R1-14B training $(date) ==="
python "$SCRIPTS/train_lora.py" \
  --dataset "$DATASET" \
  --model unsloth/DeepSeek-R1-Distill-Qwen-14B-bnb-4bit \
  --adapter-name openclaw-deepseek-r1-v1 \
  --lora-rank 32 \
  --lora-alpha 64 \
  --dropout 0 \
  --epochs 15 \
  --lr 2e-4 \
  --warmup-ratio 0.05 \
  --weight-decay 0 \
  --max-seq-len 512 \
  --batch-size 1 \
  --grad-accum 16 \
  --val-split 0 \
  --wandb-project ""
echo "=== [2/2] DeepSeek-R1-14B training finished $(date) ==="

# Evaluate DeepSeek
echo "=== [2/2] Evaluating DeepSeek-R1 adapter ==="
PYTHONUNBUFFERED=1 python "$SCRIPTS/eval_lora.py" \
  --adapter /mnt/d/lora_adapters/openclaw-deepseek-r1-v1 \
  --test "$DATASET" \
  --samples 20 \
  --max-new-tokens 256

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ALL TRAINING COMPLETE $(date)"
echo "═══════════════════════════════════════════════════════"
