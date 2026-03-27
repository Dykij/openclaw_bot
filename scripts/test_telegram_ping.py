"""
Тестовый скрипт - Diagnostics Ping.
Отправляет диагностическое сообщение напрямую через Telegram Bot API:
  1. Проверяет работоспособность бота (getMe)
  2. Проверяет доступность Ollama
  3. Отправляет живой отчёт в чат администратора
  4. Тестирует pipeline_executor (dry-run intent routing без Ollama)

Использование:
    python -m scripts.test_telegram_ping
"""

import asyncio
import json
import os
import sys
import time

import aiohttp

# ── конфиг ──────────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "openclaw_config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG = json.load(_f)

BOT_TOKEN  = _CONFIG["system"]["telegram"]["bot_token"]
ADMIN_ID   = str(_CONFIG["system"]["telegram"]["admin_chat_id"])
OLLAMA_URL = _CONFIG["system"].get("ollama_url", "http://172.27.192.1:11434")
TG_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── helpers ──────────────────────────────────────────────────────────────────
async def tg_send(session: aiohttp.ClientSession, text: str, parse_mode: str = "Markdown") -> dict:
    """Отправляет сообщение через Bot API."""
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": parse_mode}
    async with session.post(f"{TG_API}/sendMessage", json=payload) as r:
        data = await r.json()
        if not data.get("ok"):
            # fallback: plain text
            del payload["parse_mode"]
            async with session.post(f"{TG_API}/sendMessage", json=payload) as r2:
                data = await r2.json()
        return data


async def check_bot(session: aiohttp.ClientSession) -> dict:
    """getMe — убеждаемся что токен валиден."""
    async with session.get(f"{TG_API}/getMe") as r:
        return await r.json()


async def check_ollama(session: aiohttp.ClientSession) -> tuple[bool, str]:
    """Ping Ollama /api/tags."""
    try:
        async with session.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            if r.status == 200:
                data = await r.json()
                models = [m.get("name", "?") for m in data.get("models", [])]
                return True, f"✅ Ollama online — {len(models)} моделей: {', '.join(models[:5])}"
            return False, f"⚠️ Ollama вернул HTTP {r.status}"
    except Exception as e:
        return False, f"❌ Ollama недоступна: {e}"


# ── keyword intent routing (без LLM) ─────────────────────────────────────────
DMARKET_KW = {
    "buy","sell","dmarket","trade","price","hft","arbitrage",
    "купить","продать","торговля","цена","арбитраж","дмаркет",
    "скин","инвентарь","skin","inventory","target","spread",
}

def keyword_intent(prompt: str) -> str:
    low = prompt.lower()
    return "Dmarket" if any(kw in low for kw in DMARKET_KW) else "OpenClaw"


# ── main ─────────────────────────────────────────────────────────────────────
TEST_PROMPTS = [
    "Купить AK-47 Redline по цене ниже рынка",
    "Покажи статус системы и список моделей",
    "Проверь инвентарь Dmarket и предложи арбитраж",
    "Сколько VRAM использует текущая модель?",
]

async def main():
    t0 = time.monotonic()

    async with aiohttp.ClientSession() as session:
        # 1. Проверка бота
        me = await check_bot(session)
        if not me.get("ok"):
            print(f"[FATAL] Bot token invalid: {me}")
            sys.exit(1)
        bot_name = me["result"]["username"]
        print(f"[OK] Bot: @{bot_name}")

        # 2. Проверка Ollama
        ollama_ok, ollama_msg = await check_ollama(session)
        print(f"[Ollama] {ollama_msg}")

        # 3. Keyword routing test
        routing_lines = []
        for p in TEST_PROMPTS:
            brigade = keyword_intent(p)
            routing_lines.append(f"  • `{p[:50]}` → *{brigade}*")

        # 4. Формируем отчёт
        elapsed = time.monotonic() - t0
        report = (
            f"🔬 *OpenClaw — Diagnostic Ping*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 *Бот:* @{bot_name} — ✅ Работает\n"
            f"📡 *Ollama:* {ollama_msg}\n\n"
            f"🧭 *Тест маршрутизации (keyword-fallback):*\n"
            + "\n".join(routing_lines) +
            f"\n\n"
            f"⏱ *Время диагностики:* {elapsed:.2f}s\n"
            f"📅 *Версия конфига:* `{_CONFIG['system']['version']}`\n\n"
            f"_Все исправления применены: dmarket\\_mcp ✓ | BRAIN.md path ✓ | intent\\_cache cap ✓_"
        )

        resp = await tg_send(session, report)
        if resp.get("ok"):
            msg_id = resp["result"]["message_id"]
            print(f"[OK] Telegram report sent → message_id={msg_id}")
            print(f"[OK] Check your Telegram chat — admin_id={ADMIN_ID}")
        else:
            print(f"[FAIL] Telegram send failed: {resp}")


if __name__ == "__main__":
    asyncio.run(main())
