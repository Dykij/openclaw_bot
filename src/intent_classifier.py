"""
LLM-based intent classification for routing user prompts to brigades.

Extracted from OpenClawGateway to keep main.py under 500 LOC.
"""

import aiohttp
import structlog

logger = structlog.get_logger("IntentClassifier")


async def classify_intent(gateway, prompt: str) -> str:
    """
    LLM-based intent classification.
    Uses model from config (model_router.risk_analysis) for routing.
    Falls back to keyword matching if vLLM is unavailable.
    """
    # Check cache first (capped at 500 entries to prevent memory leak)
    cache_key = prompt.lower().strip()[:100]
    if cache_key in gateway._intent_cache:
        return gateway._intent_cache[cache_key]
    if len(gateway._intent_cache) >= 500:
        keys_to_drop = list(gateway._intent_cache.keys())[:250]
        for k in keys_to_drop:
            del gateway._intent_cache[k]

    # Keyword fallback (always available)
    dmarket_keywords = [
        "buy", "sell", "dmarket", "trade", "price", "hft", "arbitrage",
        "купить", "продать", "торговля", "цена", "арбитраж", "дмаркет",
        "скин", "инвентарь", "skin", "inventory", "target", "spread",
    ]
    openclaw_keywords = [
        "config", "конфиг", "pipeline", "модел", "model", "vllm",
        "бригад", "brigade", "роль", "role", "mcp", "плагин", "plugin",
        "бот", "bot", "openclaw", "gateway", "память", "memory",
    ]
    lower_prompt = prompt.lower()
    if any(kw in lower_prompt for kw in dmarket_keywords):
        keyword_result = "Dmarket"
    elif any(kw in lower_prompt for kw in openclaw_keywords):
        keyword_result = "OpenClaw"
    else:
        keyword_result = "General"

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
            f"Dmarket = trading, buying, selling items, prices, market, skins, inventory.\n"
            f"OpenClaw = system administration, framework, configuration, models, bots, pipeline.\n"
            f"General = general questions, chitchat, greetings, unrelated topics, unclear intent.\n\n"
            f"Request: {prompt}\n\n"
            f"Reply with ONLY the category name, nothing else."
        )
        payload = {
            "model": classify_model,
            "messages": [{"role": "user", "content": classify_prompt}],
            "stream": False,
            "max_tokens": 16,
        }
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.post(
                f"{gateway.vllm_url}/chat/completions", json=payload, timeout=timeout
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data["choices"][0]["message"]["content"].strip()
                    for b in all_classes:
                        if b.lower() in result.lower():
                            gateway._intent_cache[cache_key] = b
                            logger.info("Intent classified by LLM", brigade=b, raw_response=result)
                            return b
    except Exception as e:
        logger.warning("LLM intent classification failed, using keyword fallback", error=str(e))

    gateway._intent_cache[cache_key] = keyword_result
    logger.info("Intent classified by keywords", brigade=keyword_result, keyword_class=keyword_result)
    return keyword_result
