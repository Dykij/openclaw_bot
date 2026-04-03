"""
LLM-based intent classification for routing user prompts to brigades.

Extracted from OpenClawGateway to keep main.py under 500 LOC.

v17.0: LRU cache with TTL, improved typing.
"""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import structlog

from src.llm_gateway import route_llm

logger = structlog.get_logger("IntentClassifier")

# ---------------------------------------------------------------------------
# LRU Cache with TTL
# ---------------------------------------------------------------------------
_INTENT_CACHE_MAX = 500
_INTENT_CACHE_TTL = 300  # 5 minutes


class _LRUCacheTTL:
    """Simple LRU cache with TTL eviction."""

    def __init__(self, maxsize: int = _INTENT_CACHE_MAX, ttl: float = _INTENT_CACHE_TTL) -> None:
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> Optional[str]:
        """Get value if present and not expired."""
        if key not in self._cache:
            return None
        value, ts = self._cache[key]
        if time.monotonic() - ts > self._ttl:
            del self._cache[key]
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def put(self, key: str, value: str) -> None:
        """Insert or update a value."""
        self._cache[key] = (value, time.monotonic())
        self._cache.move_to_end(key)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def __len__(self) -> int:
        return len(self._cache)


# Module-level singleton cache (replaces gateway._intent_cache)
_intent_cache = _LRUCacheTTL()


# ---------------------------------------------------------------------------
# Prefix command fast-path
# ---------------------------------------------------------------------------
_PREFIX_MAP: Dict[str, str] = {
    "/dmarket": "Dmarket-Dev",
    "/research": "Research-Ops",
    "/openclaw": "OpenClaw-Core",
    "/core": "OpenClaw-Core",
    "/general": "General",
}

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------
_DMARKET_KEYWORDS = frozenset([
    "buy", "sell", "dmarket", "trade", "price", "hft", "arbitrage",
    "купить", "продать", "торговля", "цена", "арбитраж", "дмаркет",
    "скин", "инвентарь", "skin", "inventory", "target", "spread",
    "offer", "listing", "profit", "margin", "предложение",
    "маржа", "профит", "листинг",
])

_OPENCLAW_KEYWORDS = frozenset([
    "config", "конфиг", "pipeline", "модел", "model", "vllm",
    "бригад", "brigade", "роль", "role", "mcp", "плагин", "plugin",
    "бот", "bot", "openclaw", "gateway", "память", "memory",
    "clawhub", "npx", "pnpm dlx", "bunx", "npm install", "npm run",
    "npx clawhub", "install sonos", "install sono", "@latest",
    "проверь команд", "запусти команд", "выполни команд",
    "подключи", "подключена ли", "подключен ли", "проверь подключен",
    "установи", "проверь установ", "запусти", "выполни",
    "agent", "persona", "агент", "персон",
    "debug", "отлад", "research", "исследов",
    "openrouter", "опенроутер",
])

_WEB_RESEARCH_KEYWORDS = frozenset([
    "deep research", "глубокий анализ", "найди в интернете", "найди в сети",
    "поищи в интернете", "поищи в сети", "веб-поиск", "вебпоиск",
    "найди информацию о", "прочитай статью", "открой ссылку",
    "перейди по ссылке", "загрузи страницу", "проверь сайт",
])


def _keyword_classify(prompt: str) -> str:
    """Classify intent using keyword matching (zero-latency fallback)."""
    lower = prompt.lower()
    has_url = bool(re.search(r"https?://", lower))
    if any(kw in lower for kw in _DMARKET_KEYWORDS):
        return "Dmarket-Dev"
    if has_url or any(kw in lower for kw in _WEB_RESEARCH_KEYWORDS):
        return "Research-Ops"
    if any(kw in lower for kw in _OPENCLAW_KEYWORDS):
        return "OpenClaw-Core"
    return "General"


async def classify_intent(gateway: Any, prompt: str) -> str:
    """
    LLM-based intent classification with LRU cache + TTL.

    Uses model from config (model_router.risk_analysis) for routing.
    Falls back to keyword matching if LLM is unavailable.

    v14.4: Fast-Intent — prefix commands bypass LLM entirely.
    v17.0: LRU cache with TTL replaces FIFO dict.
    """
    # v14.4: Prefix command fast-path — zero latency routing
    stripped = prompt.strip()
    for prefix, brigade in _PREFIX_MAP.items():
        if stripped.lower().startswith(prefix):
            logger.info("Intent fast-path: prefix command", prefix=prefix, brigade=brigade)
            return brigade

    # Check LRU cache
    cache_key = prompt.lower().strip()[:100]
    cached = _intent_cache.get(cache_key)
    if cached is not None:
        return cached

    # Keyword fallback (always available)
    keyword_result = _keyword_classify(prompt)

    # Try LLM-based classification
    classify_model = (
        gateway.config.get("system", {}).get("model_router", {}).get("risk_analysis")
        or next(
            (
                d["model"]
                for brigade in gateway.config.get("brigades", {}).values()
                for d in brigade.get("roles", {}).values()
            ),
            "llama3.2",
        )
    )

    try:
        brigades = list(gateway.config.get("brigades", {}).keys())
        all_classes = brigades + ["General"]
        classify_prompt = (
            f"Classify this user request into ONE of these categories: {', '.join(all_classes)}.\n"
            f"Dmarket-Dev = trading, buying, selling items, prices, market, skins, inventory.\n"
            f"OpenClaw-Core = system administration, framework, configuration, models, bots, pipeline, "
            f"CLI commands execution (npx, pnpm, bunx, npm), clawhub, installing packages, "
            f"running shell commands, checking connections, verifying installations.\n"
            f"Research-Ops = web search, research, URLs, browsing the internet, fetching URLs, "
            f"deep research, analysis, reports, benchmarks.\n"
            f"General = general questions, chitchat, greetings, unrelated topics, unclear intent.\n\n"
            f"Request: {prompt}\n\n"
            f"Reply with ONLY the category name, nothing else."
        )

        raw = await route_llm(
            classify_prompt,
            task_type="intent",
            max_tokens=16,
            temperature=0.0,
        )
        if raw:
            for b in all_classes:
                if b.lower() in raw.lower():
                    _intent_cache.put(cache_key, b)
                    logger.info("Intent classified by LLM Gateway", brigade=b, raw_response=raw)
                    return b
    except Exception as e:
        logger.warning("LLM intent classification failed, using keyword fallback", error=str(e))

    _intent_cache.put(cache_key, keyword_result)
    logger.info("Intent classified by keywords", brigade=keyword_result, keyword_class=keyword_result)
    return keyword_result
