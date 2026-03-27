# Architectural Consolidation & Elite Free-Tier Optimization

**Date:** 2025-07-19  
**Author:** OpenClaw Engineering

---

## Summary

This release completes a major architectural consolidation of the OpenClaw bot gateway, decomposing two monolithic modules totalling 1,600+ LOC into purpose-built packages, tuning the SmartModelRouter scoring for elite free-tier models, and doubling the token budget ceiling to 16k.

## What Changed

### 1. `src/main.py` → `src/boot/`

The 811-line `main.py` contained environment setup (structlog, Prometheus metrics, PID lock, config file watching) and a ~120-line `run()` initialization sequence. These responsibilities are now split into:

| Module          | Responsibility                                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_env_setup.py` | Prometheus counters/gauges, `setup_structlog()`, `ConfigReloader`, file lock                                                                                        |
| `_mcp_init.py`  | `configure_llm_and_pipeline()` — 10-step async init: LLM gateway, pipeline, HITL, dashboard, background tasks, scheduler, Discord, vLLM/cloud startup, Brigade REST |

`main.py` now imports from `src.boot` and delegates initialization in four lines. Net reduction: **~200 LOC** removed from the hot path.

### 2. `src/gateway_commands.py` → `src/handlers/commands/`

The 798-line command monolith is replaced by a 23-line facade. The existing `src/bot_commands/` package (status, callbacks, research, diagnostics, media, agents) already had the decomposed implementations — the new `src/handlers/commands/` provides a unified namespace re-exporting from there.

| Module          | Handlers                                                                                  |
| --------------- | ----------------------------------------------------------------------------------------- |
| `_admin.py`     | `cmd_help`, `cmd_start`, `cmd_status`, `cmd_models`, `cmd_history`, `cmd_perf`, callbacks |
| `_tools.py`     | `cmd_tailscale`, `cmd_test`, `cmd_test_all_models`, `cmd_research`                        |
| `_media.py`     | `handle_photo`, `handle_voice`, `handle_document`, audio transcription, PDF extraction    |
| `_ai_config.py` | `cmd_agents`, `cmd_agent`, `cmd_openrouter_test`                                          |

### 3. Model Router Optimization

Updated `config/openclaw_config.json` model_router for elite free-tier performance:

| Task      | Before                                   | After                              |
| --------- | ---------------------------------------- | ---------------------------------- |
| code      | `meta-llama/llama-3.3-70b-instruct:free` | `qwen/qwen-2.5-coder-32b-instruct` |
| reasoning | `deepseek/deepseek-r1:free`              | _(unchanged)_                      |
| general   | `meta-llama/llama-3.3-70b-instruct:free` | _(unchanged)_                      |
| vision    | `meta-llama/llama-4-maverick:free`       | _(unchanged)_                      |

**Why Qwen-2.5-Coder-32B?** Benchmarks show it outperforms Llama-3.3-70B on HumanEval (92.7 vs 88.4) and MBPP+ while using significantly fewer parameters. For code-specific routing, a specialized 32B coder beats a generalist 70B.

### 4. SmartRouter Weight Tuning

Scoring adjustments in `src/ai/inference/router.py`:

- **Capability match bonus:** 3.0 → **4.0** — stronger specialization preference
- **Quality ceiling:** high tier 2.0 → **2.5** — elite models score higher
- **Complex task quality weight:** 1.5 → **2.0** — complex prompts strongly prefer quality
- **Complex task speed weight:** 0.5 → **0.3** — less speed pressure for hard problems

Net effect: the router now **strongly** routes code to Qwen, reasoning to DeepSeek-R1, and only falls back to Llama for general/unclassified tasks.

### 5. Token Budget: 8k → 16k

`vllm_max_model_len` doubled from 8192 to 16384. The `AdaptiveTokenBudget` automatically scales per-request budgets from this ceiling:

- **research** tasks now get up to 16384 tokens (was 8192)
- **code** tasks get 2048 (limited by task-type default, not ceiling)
- **general** tasks get 256 (concise by design)

## Validation

The holistic stress test (`scripts/stress_test_decomposition.py`) passes all 34 checks:

- **18** import integrity tests across all decomposed packages
- **6** routing accuracy tests confirming correct model selection per task type
- **5** token budget tests validating the 16k ceiling
- **4** module structure checks (all expected files present)
- **1** config consistency check

Results logged to `data/runtime_error_log.json`.

## Architecture After

```
src/
  boot/
    _env_setup.py      # Metrics, structlog, config watcher, PID lock
    _mcp_init.py       # Async 10-step gateway initialization
  handlers/
    commands/           # Unified command namespace
      _admin.py         # System/admin commands
      _tools.py         # Utility commands
      _media.py         # Photo/voice/document handlers
      _ai_config.py     # AI configuration commands
  pipeline/             # Decomposed from pipeline_executor.py (1120 LOC → 5 modules)
  research/             # Decomposed from deep_research.py (934 LOC → 5 modules)
  ai/inference/
    router.py           # SmartModelRouter (tuned weights)
    budget.py           # AdaptiveTokenBudget (16k ceiling)
  main.py               # Thin entry point (~610 LOC, down from 811)
  gateway_commands.py   # 23-line facade
```

Total monolith LOC decomposed across all phases: **~3,660 LOC** (main 811 + gateway_commands 798 + pipeline_executor 1120 + deep_research 934).
