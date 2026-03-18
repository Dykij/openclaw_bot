#!/usr/bin/env python3
"""
Setup script for GRPO/LoRA training environment.

Installs training dependencies into a separate virtualenv
to keep the inference environment clean.

Target: WSL2 Ubuntu on NVIDIA RTX 5060 Ti (16GB VRAM)
"""

import os
import subprocess
import sys
from pathlib import Path


# Default paths (WSL2 convention)
DEFAULT_VENV_DIR = "/mnt/d/training_env"
DEFAULT_MODELS_DIR = "/mnt/d/vllm_models"
DEFAULT_ADAPTERS_DIR = "/mnt/d/lora_adapters"
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "training_data")

TRAINING_DEPS = [
    "torch",
    "unsloth",
    "bitsandbytes",
    "accelerate",
    "xformers",
    "peft",
    "trl",
    "datasets",
    "huggingface_hub",
    "sentencepiece",
    "transformers",
]


def check_nvidia_gpu():
    """Check if NVIDIA GPU is available."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip()
            print(f"✅ GPU detected: {gpu_info}")
            return True
        print("❌ nvidia-smi failed — no GPU detected")
        return False
    except FileNotFoundError:
        print("❌ nvidia-smi not found — NVIDIA drivers not installed")
        return False
    except subprocess.TimeoutExpired:
        print("❌ nvidia-smi timed out")
        return False


def create_venv(venv_dir: str):
    """Create a Python virtual environment for training."""
    venv_path = Path(venv_dir)
    if venv_path.exists():
        print(f"⚠️  Virtualenv already exists: {venv_dir}")
        return

    print(f"📦 Creating virtualenv at {venv_dir}...")
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_path)],
        check=True,
    )
    print(f"✅ Virtualenv created: {venv_dir}")


def install_deps(venv_dir: str):
    """Install training dependencies into virtualenv."""
    pip = os.path.join(venv_dir, "bin", "pip")
    if not os.path.exists(pip):
        pip = os.path.join(venv_dir, "Scripts", "pip.exe")

    print(f"📦 Installing training dependencies...")
    subprocess.run(
        [pip, "install", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [pip, "install"] + TRAINING_DEPS,
        check=True,
    )
    print(f"✅ Dependencies installed: {', '.join(TRAINING_DEPS)}")


def create_directories():
    """Create required directories for training data and adapters."""
    dirs = [DEFAULT_DATA_DIR, DEFAULT_ADAPTERS_DIR]
    for d in dirs:
        path = Path(d)
        path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Directory ready: {d}")


def check_existing_deps():
    """Check which training deps are already available in current env."""
    available = {}
    for dep in TRAINING_DEPS:
        try:
            __import__(dep.replace("-", "_"))
            available[dep] = True
        except ImportError:
            available[dep] = False

    installed = [k for k, v in available.items() if v]
    missing = [k for k, v in available.items() if not v]

    if installed:
        print(f"✅ Already available: {', '.join(installed)}")
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")

    return available


def print_setup_summary():
    """Print setup summary and next steps."""
    print("\n" + "=" * 60)
    print("🎓 GRPO/LoRA Training Environment Setup Complete")
    print("=" * 60)
    print(f"""
Directories:
  Training data:  {DEFAULT_DATA_DIR}
  LoRA adapters:  {DEFAULT_ADAPTERS_DIR}
  Models:         {DEFAULT_MODELS_DIR}

Next Steps:
  1. Collect training data:
     python -m src.interaction_logger --mode collect

  2. Compute rewards:
     python -m src.reward_verifier --data training_data/

  3. Check dependencies:
     python -m src.grpo_trainer --check-deps

  4. Dry run (generate training plan):
     python -m src.grpo_trainer --dry-run \\
       --model Qwen/Qwen2.5-Coder-7B-Instruct \\
       --data training_data/interactions.jsonl

  5. Full training (STOP vLLM FIRST):
     python -m src.grpo_trainer \\
       --model Qwen/Qwen2.5-Coder-7B-Instruct \\
       --data training_data/interactions.jsonl \\
       --output lora_adapters/qwen-coder-7b/ \\
       --epochs 3 --batch-size 2

⚠️  IMPORTANT: Stop vLLM inference before training!
    Training and inference cannot coexist on 16GB VRAM.
""")


def main():
    print("🔧 OpenClaw GRPO/LoRA Training Setup")
    print("=" * 60)

    # Step 1: Check GPU
    has_gpu = check_nvidia_gpu()

    # Step 2: Check existing deps
    print("\n📋 Checking existing dependencies...")
    check_existing_deps()

    # Step 3: Create directories
    print("\n📁 Creating directories...")
    create_directories()

    # Step 4: Summary
    print_setup_summary()

    if not has_gpu:
        print("⚠️  No GPU detected. Training will only work on GPU-equipped machines.")
        print("   This setup created directories and checked dependencies.")


if __name__ == "__main__":
    main()
