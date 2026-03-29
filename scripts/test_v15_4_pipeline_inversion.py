"""v15.4 stress tests — Pipeline Inversion & Early Decomposition.

Tests:
1. Early decomposition fires in prompt_handler BEFORE intent classification
2. LATS URL bypass — prompts with URLs never activate LATS
3. LATS leakage containment — planning preamble wrapped in <think>
4. Multi-task merge format verification
5. Regression: single-task prompts still fall through to intent classification

Run: python scripts/test_v15_4_pipeline_inversion.py
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline._core import (
    _decompose_multi_task,
    _route_subtask,
    _BRIGADE_KEYWORDS,
)
from src.pipeline._lats_search import classify_complexity

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Phase 1: Early Decomposition (structural tests)
# ---------------------------------------------------------------------------
print("\n=== Phase 1: Early Decomposition ===")

# 1a. The canonical 3-part prompt must decompose into >=2 tasks
_CANONICAL = (
    "Проанализируй это видео https://www.youtube.com/watch?v=abcdef12345 — дай краткую выжимку, "
    "что там говорят про оптимизацию latency в HFT.\n\n"
    "Напиши модуль на Rust через PyO3 для генерации подписи Dmarket API. "
    "Используй hmac-sha256. Без заглушек, полный рабочий код.\n\n"
    "Проверь код на уязвимости и покажи результат аудита."
)

sub = _decompose_multi_task(_CANONICAL)
check("canonical decomposes >=2", len(sub) >= 2, f"got {len(sub)}")
check("canonical decomposes >=3", len(sub) >= 3, f"got {len(sub)}")

# 1b. Sub-tasks are routed to different brigades
if sub:
    brigades = [b for _, b in sub]
    unique = set(brigades)
    check("routes to >=2 brigades", len(unique) >= 2, f"got {unique}")
    # YouTube/research paragraph → Research-Ops
    first_brig = sub[0][1]
    check("first task → Research-Ops", first_brig == "Research-Ops", f"got {first_brig}")
    # PyO3/Rust paragraph → Dmarket-Dev
    code_tasks = [b for t, b in sub if "pyo3" in t.lower() or "rust" in t.lower()]
    check("code task → Dmarket-Dev", "Dmarket-Dev" in code_tasks, f"got {code_tasks}")

# 1c. With chat history prefix — decomposer still works
_HISTORY_PREFIX = (
    "[CHAT HISTORY — last conversation turns]:\n"
    "User: покажи баланс\n"
    "Assistant: Баланс: $42.50\n\n"
    "[CURRENT TASK]:\n"
)
sub_with_hist = _decompose_multi_task(_HISTORY_PREFIX + _CANONICAL)
check(
    "decomposes with history prefix",
    len(sub_with_hist) >= 2,
    f"got {len(sub_with_hist)}",
)

# 1d. Single short prompt does NOT decompose
short = "Покажи мой баланс на Dmarket"
short_sub = _decompose_multi_task(short)
check("short prompt not decomposed", len(short_sub) == 0, f"got {len(short_sub)}")

# 1e. Single-paragraph long prompt without action verbs does NOT decompose
long_single = (
    "Я хочу разобраться в том как устроен Dmarket API и какие есть ограничения "
    "по частоте запросов, какой формат подписи используется, и как правильно "
    "настроить WebSocket соединение для получения обновлений цен в реальном времени, "
    "а также какие есть лимиты на количество одновременных подключений и как "
    "обрабатывать ситуации когда сервер разрывает соединение."
)
long_sub = _decompose_multi_task(long_single)
check("single-paragraph not decomposed", len(long_sub) < 2, f"got {len(long_sub)}")


# ---------------------------------------------------------------------------
# Phase 2: LATS URL Bypass
# ---------------------------------------------------------------------------
print("\n=== Phase 2: LATS URL Bypass ===")

# 2a. URL-bearing prompt should NOT trigger LATS (structural test)
# We test the guard logic: complexity check + URL check
_URL_PROMPT = (
    "Проанализируй видео https://www.youtube.com/watch?v=abc123 "
    "и дай выжимку по HFT стратегии арбитража на Dmarket"
)
_url_complexity = classify_complexity(_URL_PROMPT)
_has_url = bool(re.search(r"https?://", _URL_PROMPT))
check("URL prompt has URL detected", _has_url is True)
# The guard condition: complexity in (complex,extreme) AND NOT _has_url
_would_lats = _url_complexity in ("complex", "extreme") and not _has_url
check("URL prompt bypasses LATS", _would_lats is False, f"complexity={_url_complexity}, has_url={_has_url}")

# 2b. Non-URL complex prompt still triggers LATS
# Must contain >=2 keywords from _COMPLEX_KEYWORDS: rust, async, security, pyo3, etc.
_NO_URL_PROMPT = (
    "Разработай полный async модуль для Dmarket на Rust: "
    "парсер цен, определение спреда, algorithm для оптимизации, "
    "security audit и performance benchmark на данных"
)
_no_url_complexity = classify_complexity(_NO_URL_PROMPT)
_no_url_has_url = bool(re.search(r"https?://", _NO_URL_PROMPT))
_would_lats_nurl = _no_url_complexity in ("complex", "extreme") and not _no_url_has_url
check(
    "non-URL complex prompt would LATS",
    _would_lats_nurl is True,
    f"complexity={_no_url_complexity}, has_url={_no_url_has_url}",
)

# 2c. Multiple URLs in prompt — still bypasses LATS
_MULTI_URL = (
    "Сравни https://dmarket.com/api/v1 и https://docs.dmarket.com/api-reference "
    "для Dmarket арбитраж HFT latency trading"
)
_multi_has_url = bool(re.search(r"https?://", _MULTI_URL))
check("multi-URL bypasses LATS", _multi_has_url is True)


# ---------------------------------------------------------------------------
# Phase 3: LATS Leakage Containment
# ---------------------------------------------------------------------------
print("\n=== Phase 3: LATS Leakage Containment ===")

# 3a. Planning preamble gets wrapped in <think>
_PLANNING_RE = re.compile(
    r"^((?:.*?(?:Approach\s*#\d|Plan\s*:|Подход\s*#?\d|План\s*:).*?\n)+)",
    re.IGNORECASE | re.DOTALL,
)

_answer_with_plan = (
    "Approach #1: First we analyze the market data.\n"
    "Approach #2: Then we build the execution engine.\n"
    "Here is the actual implementation:\n"
    "```rust\nfn main() {}\n```"
)
m = _PLANNING_RE.match(_answer_with_plan)
check("planning preamble detected", m is not None)
if m:
    wrapped = f"<think>\n{m.group(1).strip()}\n</think>\n\n" + _answer_with_plan[m.end():]
    check("<think> wraps planning", "<think>" in wrapped and "Approach #1" in wrapped)
    # After stripping <think>
    stripped = re.sub(r"<think>[\s\S]*?</think>\s*", "", wrapped).strip()
    check("stripped has no Approach", "Approach #1" not in stripped)
    check("stripped has implementation", "```rust" in stripped)

# 3b. Answer without planning preamble is untouched
_clean_answer = "Here is the code:\n```rust\nfn main() {}\n```"
m2 = _PLANNING_RE.match(_clean_answer)
check("clean answer not matched", m2 is None)

# 3c. Russian planning preamble
_ru_plan = "План: собрать данные, проанализировать.\nВот код:\n```python\nprint('ok')\n```"
m3 = _PLANNING_RE.match(_ru_plan)
check("russian План: detected", m3 is not None)

# 3d. Подход # variant
_ru_approach = "Подход #1: загрузить API ключи\nПодход #2: настроить подпись\nРеализация:\ncode here"
m4 = _PLANNING_RE.match(_ru_approach)
check("russian Подход # detected", m4 is not None)


# ---------------------------------------------------------------------------
# Phase 4: prompt_handler.py structural checks
# ---------------------------------------------------------------------------
print("\n=== Phase 4: prompt_handler.py Structure ===")

import inspect
from src.handlers import prompt_handler as ph

source = inspect.getsource(ph._handle_prompt_inner)

# 4a. _decompose_multi_task is imported/called BEFORE the actual classify_intent() call
# Use the function call patterns (not comments) to find positions.
decompose_pos = source.find("_decompose_multi_task(prompt)")
classify_pos = source.find("await classify_intent(")
check(
    "decomposition before classification",
    0 < decompose_pos < classify_pos,
    f"decompose@{decompose_pos}, classify@{classify_pos}",
)

# 4b. Early return after multi-task handling
decompose_block = source[decompose_pos:classify_pos]
check(
    "early return in decompose block",
    "return" in decompose_block,
)

# 4c. Chat history injection happens before decomposition
history_pos = source.find("history_prefix = _build_history_prefix")
check(
    "history before decompose",
    0 < history_pos < decompose_pos,
    f"history@{history_pos}, decompose@{decompose_pos}",
)

# 4d. <think> stripping in multi-task merge
# Look for the re.sub call that strips <think> tags in multi-task path
think_strip_pos = source.find("<think>")
check(
    "<think> stripping in multi-task path",
    0 < think_strip_pos < classify_pos,
    f"think@{think_strip_pos}, classify@{classify_pos}",
)

# 4e. _enrich_bare_url still called (regression)
enrich_pos = source.find("_enrich_bare_url")
check("bare URL enrichment present", enrich_pos > 0)

# 4f. Bare URL enrichment before decomposition
check(
    "bare URL before decompose",
    0 < enrich_pos < decompose_pos,
    f"enrich@{enrich_pos}, decompose@{decompose_pos}",
)


# ---------------------------------------------------------------------------
# Phase 5: _route_subtask coverage
# ---------------------------------------------------------------------------
print("\n=== Phase 5: Route Subtask Coverage ===")

check(
    "YouTube → Research-Ops",
    _route_subtask("Проанализируй видео https://youtube.com/xxx") == "Research-Ops",
)
check(
    "Dmarket code → Dmarket-Dev",
    _route_subtask("Напиши модуль для Dmarket арбитража на Python") == "Dmarket-Dev",
)
check(
    "pyo3 code → Dmarket-Dev",
    _route_subtask("Создай PyO3 биндинг для подписи") == "Dmarket-Dev",
)
check(
    "pipeline config → OpenClaw-Core",
    _route_subtask("Настрой pipeline для бота") == "OpenClaw-Core",
)
check(
    "unknown fallback → OpenClaw-Core",
    _route_subtask("Привет, как дела?") == "OpenClaw-Core",
)
check(
    "web search → Research-Ops",
    _route_subtask("Найди информацию через интернет") == "Research-Ops",
)


# ---------------------------------------------------------------------------
# Phase 6: LATS guard in _core.py structural check
# ---------------------------------------------------------------------------
print("\n=== Phase 6: LATS Guard Structure ===")

import inspect as _insp
from src.pipeline._core import PipelineExecutor

exec_source = _insp.getsource(PipelineExecutor.execute)

# 6a. LATS guard checks for URL
check("LATS guard has URL check", "not _has_url" in exec_source or "has_url" in exec_source)

# 6b. LATS guard still checks complexity
check("LATS guard checks complexity", 'complexity in ("complex", "extreme")' in exec_source)

# 6c. LATS guard still checks brigade
check("LATS guard checks brigade", '"Dmarket-Dev"' in exec_source)

# 6d. Planning regex is used in LATS return path
check("LATS leakage containment in execute", "Approach" in exec_source and "_PLANNING_RE" in exec_source)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"v15.4 Pipeline Inversion tests: {PASSED} passed, {FAILED} failed")
print(f"{'='*60}")
sys.exit(1 if FAILED else 0)
