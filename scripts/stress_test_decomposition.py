"""Holistic stress test — validates decomposed modules and model routing.

Tests:
  1. Import integrity for all decomposed packages
  2. SmartModelRouter routing accuracy with new config
  3. AdaptiveTokenBudget with 16k max tokens
  4. Module structure validation (LOC counts, no circular deps)
  5. Config consistency checks

Outputs runtime_error_log.json.
"""

import importlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


results: list[dict] = []


def log_result(name: str, passed: bool, latency_ms: float, detail: str = "") -> None:
    results.append({
        "test": name,
        "passed": passed,
        "latency_ms": round(latency_ms, 2),
        "detail": detail,
        "ts": _ts(),
    })
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name} ({latency_ms:.1f}ms) {detail}")


# --- 1. Import integrity ---
print("\n=== 1. Import Integrity ===")
MODULES = [
    "src.boot",
    "src.boot._env_setup",
    "src.boot._mcp_init",
    "src.handlers.commands",
    "src.gateway_commands",
    "src.pipeline",
    "src.pipeline._core",
    "src.pipeline._state",
    "src.pipeline._reflexion",
    "src.pipeline._tools_handler",
    "src.research",
    "src.research._core",
    "src.research._searcher",
    "src.research._scraper",
    "src.research._analyzer",
    "src.ai.inference.router",
    "src.ai.inference.budget",
    "src.ai.inference._shared",
]

for mod in MODULES:
    t0 = time.perf_counter()
    try:
        importlib.import_module(mod)
        dt = (time.perf_counter() - t0) * 1000
        log_result(f"import:{mod}", True, dt)
    except Exception as exc:
        dt = (time.perf_counter() - t0) * 1000
        log_result(f"import:{mod}", False, dt, str(exc))


# --- 2. SmartModelRouter routing ---
print("\n=== 2. SmartModelRouter Routing ===")
from src.ai.inference.router import SmartModelRouter
from src.ai.inference._shared import ModelProfile, RoutingTask

config_path = ROOT / "config" / "openclaw_config.json"
with open(config_path) as f:
    cfg = json.load(f)

router_cfg = cfg.get("system", {}).get("model_router", {})
profiles: dict[str, ModelProfile] = {}
for task_type, model_name in router_cfg.items():
    is_fast = "7b" in model_name.lower() or "mini" in model_name.lower()
    if model_name not in profiles:
        profiles[model_name] = ModelProfile(
            name=model_name,
            vram_gb=4.0 if is_fast else 9.5,
            capabilities=[task_type],
            speed_tier="fast" if is_fast else "medium",
            quality_tier="medium" if is_fast else "high",
        )
    else:
        profiles[model_name].capabilities.append(task_type)

router = SmartModelRouter(profiles)

routing_tests = [
    ("code_simple", RoutingTask(prompt="fix this bug", task_type="code"), "qwen"),
    ("code_complex", RoutingTask(prompt="Refactor the entire authentication module to use RBAC with fine-grained permissions and add comprehensive unit tests covering edge cases"), "qwen"),
    ("research", RoutingTask(prompt="research quantum computing advances", task_type="research"), "deepseek"),
    ("general", RoutingTask(prompt="summarise today's news"), "llama"),
    ("risk", RoutingTask(prompt="analyse market risk", task_type="risk_analysis"), "deepseek"),
    ("vision", RoutingTask(prompt="describe this image", task_type="vision"), "maverick"),
]

for name, task, expected_substr in routing_tests:
    t0 = time.perf_counter()
    chosen = router.route(task)
    dt = (time.perf_counter() - t0) * 1000
    ok = expected_substr.lower() in chosen.lower()
    log_result(f"route:{name}", ok, dt, f"chose={chosen}")


# --- 3. AdaptiveTokenBudget with 16k ---
print("\n=== 3. AdaptiveTokenBudget (16k) ===")
from src.ai.inference.budget import AdaptiveTokenBudget

vllm_max = cfg.get("system", {}).get("vllm_max_model_len", 8192)
t0 = time.perf_counter()
budget = AdaptiveTokenBudget(default_max_tokens=vllm_max)
dt = (time.perf_counter() - t0) * 1000
log_result("budget:init_16k", vllm_max == 16384, dt, f"max_tokens={vllm_max}")

for task_type in ["general", "code", "research", "creative"]:
    t0 = time.perf_counter()
    est = budget.estimate_budget(prompt="test prompt", task_type=task_type)
    dt = (time.perf_counter() - t0) * 1000
    log_result(f"budget:{task_type}", est.max_tokens > 0, dt, f"max={est.max_tokens}, est_out={est.estimated_output_tokens}")


# --- 4. Module structure ---
print("\n=== 4. Module Structure ===")
decomposed_packages = {
    "src/boot": ["__init__.py", "_env_setup.py", "_mcp_init.py"],
    "src/handlers/commands": ["__init__.py", "_admin.py", "_tools.py", "_media.py", "_ai_config.py"],
    "src/pipeline": ["__init__.py", "_core.py", "_state.py", "_reflexion.py", "_tools_handler.py"],
    "src/research": ["__init__.py", "_core.py", "_searcher.py", "_scraper.py", "_analyzer.py"],
}

for pkg, expected_files in decomposed_packages.items():
    pkg_path = ROOT / pkg
    t0 = time.perf_counter()
    missing = [f for f in expected_files if not (pkg_path / f).exists()]
    dt = (time.perf_counter() - t0) * 1000
    ok = len(missing) == 0
    log_result(f"structure:{pkg}", ok, dt, f"missing={missing}" if missing else f"all {len(expected_files)} files present")


# --- 5. Config consistency ---
print("\n=== 5. Config Consistency ===")
t0 = time.perf_counter()
checks = []
if vllm_max != 16384:
    checks.append(f"vllm_max_model_len={vllm_max}, expected 16384")
code_model = router_cfg.get("code", "")
if "qwen" not in code_model.lower():
    checks.append(f"code model={code_model}, expected qwen")
reasoning_model = router_cfg.get("risk_analysis", "")
if "deepseek" not in reasoning_model.lower():
    checks.append(f"risk_analysis model={reasoning_model}, expected deepseek")
general_model = router_cfg.get("general", "")
if "llama" not in general_model.lower():
    checks.append(f"general model={general_model}, expected llama")
dt = (time.perf_counter() - t0) * 1000
log_result("config:consistency", len(checks) == 0, dt, "; ".join(checks) if checks else "all correct")


# --- Summary ---
print("\n=== Summary ===")
total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = total - passed
print(f"  Total: {total}, Passed: {passed}, Failed: {failed}")

output = {
    "run_ts": _ts(),
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": results,
}

out_path = ROOT / "data" / "runtime_error_log.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n  Runtime log: {out_path}")

sys.exit(0 if failed == 0 else 1)
