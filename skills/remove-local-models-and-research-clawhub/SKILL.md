---
name: remove-local-models-and-research-clawhub
description: "Cloud migration playbook: remove local model references (vLLM, LoRA, Unsloth), switch to OpenRouter cloud-only architecture, clean up GPU dependencies. Use when: migrating from local to cloud inference, cleaning legacy model code."
version: 1.0.0
---

# Cloud Migration Playbook

## Purpose

Guide for migrating from local model inference (vLLM, LoRA, Unsloth) to cloud-only (OpenRouter).

## Migration Checklist

1. Remove vLLM server launch scripts
2. Remove GPU dependency installs (CUDA, cuDNN, vLLM pip)
3. Replace all `vllm_url` configs with `openrouter_url`
4. Update system prompts mentioning local models
5. Remove LoRA/Unsloth training code (if not needed)
6. Update CI/CD to remove GPU steps
7. Update docs to reflect cloud-only architecture

## Search Patterns

```bash
# Find all vLLM references
grep -rn "vllm\|vLLM\|v_llm" --include="*.py" --include="*.md" --include="*.json"

# Find local model paths
grep -rn "localhost:8000\|WSL\|cuda\|VRAM" --include="*.py" --include="*.md"
```

## Replacement Map

| Old (local)                | New (cloud)                    |
| -------------------------- | ------------------------------ |
| `vllm_url`                 | `openrouter_url`               |
| `http://localhost:8000/v1` | `https://openrouter.ai/api/v1` |
| `vllm_manager`             | `openrouter_client`            |
| `start_vllm.sh`            | (remove)                       |
| LoRA/Unsloth refs          | (remove or archive)            |
