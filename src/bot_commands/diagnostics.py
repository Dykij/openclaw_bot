"""Diagnostics: test, test_all_models, perf, history, openrouter_test, tailscale."""

import asyncio

import aiohttp
import structlog
from aiogram.types import Message

logger = structlog.get_logger("BotCommands.Diagnostics")


async def cmd_tailscale(gateway, message: Message):
    """Show Tailscale VPN status."""
    if message.from_user.id != gateway.admin_id:
        return
    if not hasattr(gateway, 'tailscale') or gateway.tailscale is None:
        await message.reply("⚠️ Tailscale не инициализирован.", parse_mode="HTML")
        return
    status = await gateway.tailscale.get_status()
    msg = gateway.tailscale.format_status_message(status)
    await message.reply(msg, parse_mode="HTML")


async def cmd_test(gateway, message: Message):
    if message.from_user.id != gateway.admin_id:
        return

    await message.reply(
        "🔬 Запускаю VRAM-тестирование всех моделей...\nЭто может занять 10-20 минут.",
        parse_mode="Markdown",
    )

    try:
        process = await asyncio.create_subprocess_exec(
            "python",
            "pull_and_test.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=".",
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            await message.reply(
                "✅ VRAM-тест завершён! Результаты отправлены в чат.", parse_mode="Markdown"
            )
        else:
            error = stderr.decode()[:500] if stderr else "Unknown error"
            await message.reply(
                f"❌ Ошибка тестирования:\n```\n{error}\n```", parse_mode="Markdown"
            )
    except Exception as e:
        await message.reply(f"❌ Не удалось запустить тест: `{e}`", parse_mode="Markdown")


async def cmd_test_all_models(gateway, message: Message):
    if message.from_user.id != gateway.admin_id:
        return

    status_msg = await message.reply(
        "🚀 *Начинаю тестирование 20 моделей!*\n\nКаждая из ролей сейчас пройдет проверку отклика, чтобы подтвердить свои эмоции и характер. Ожидайте...",
        parse_mode="Markdown",
    )

    final_report = "📊 *Отчет: Парад Планет (20 Ролей)*\n\n"

    async def fetch_hello(session, role_name, model_name, sys_prompt):
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": f"{sys_prompt}. Представься одним коротким предложением (максимум 5-7 слов), используя свои эмодзи.",
                },
                {"role": "user", "content": "Привет, проверка связи!"},
            ],
            "stream": False,
            "max_tokens": 128,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.post(
                f"{gateway.vllm_url}/chat/completions", json=payload, timeout=timeout
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip().replace("\n", " ")
                else:
                    return f"⚠️ Ошибка vLLM ({resp.status})"
        except Exception as e:
            return f"❌ Error: {e}"

    async with aiohttp.ClientSession() as session:
        for brigade_name, brigade_info in gateway.config["brigades"].items():
            final_report += f"🏴 *Бригада: {brigade_name}*\n"

            for role, data in brigade_info["roles"].items():
                sys_prompt = data.get("system_prompt", "Обычный ассистент")
                model_name = data.get("model")

                await gateway.archivist.send_status(role, model_name, "Пингую vLLM...")

                response_text = await fetch_hello(session, role, model_name, sys_prompt)
                final_report += f"• `{role}`: {response_text}\n"

            final_report += "\n"

    await gateway.archivist.send_summary("Результаты тестирования всех ролей", final_report)
    await status_msg.edit_text(
        "✅ *Тестирование завершено!*\nВсе данные отправлены.", parse_mode="Markdown"
    )


async def cmd_history(gateway, message: Message):
    """Show recent pipeline execution history."""
    if message.from_user.id != gateway.admin_id:
        return

    history = getattr(gateway, '_pipeline_history', [])
    if not history:
        await message.reply("📜 История пуста — ещё не было выполненных задач.")
        return

    msg = "📜 *Последние задачи:*\n\n"
    for i, entry in enumerate(history[-10:], 1):
        ts = entry.get("timestamp", "?")
        brigade = entry.get("brigade", "?")
        prompt_short = entry.get("prompt", "?")[:60]
        chain = entry.get("chain", "?")
        duration = entry.get("duration_sec", 0)
        status = entry.get("status", "?")
        icon = "✅" if status == "completed" else "❌"

        msg += (
            f"{icon} *{i}.* `{ts}`\n"
            f"   📋 {prompt_short}...\n"
            f"   🏴 {brigade} | ⛓ {chain} | ⏱ {duration:.1f}s\n\n"
        )

    try:
        await message.reply(msg, parse_mode="Markdown")
    except Exception:
        await message.reply(msg.replace("*", "").replace("`", ""))


async def cmd_perf(gateway, message: Message):
    """Show inference performance metrics."""
    if message.from_user.id != gateway.admin_id:
        return

    metrics = getattr(gateway, '_perf_metrics', [])
    if not metrics:
        await message.reply("⚡ Метрики пусты — ещё не было inference вызовов.")
        return

    total_calls = len(metrics)
    total_tokens = sum(m.get("tokens", 0) for m in metrics)
    total_time = sum(m.get("duration_sec", 0) for m in metrics)
    avg_toks = total_tokens / total_time if total_time > 0 else 0
    avg_latency = total_time / total_calls if total_calls > 0 else 0

    role_stats = {}
    for m in metrics:
        role = m.get("role", "unknown")
        if role not in role_stats:
            role_stats[role] = {"calls": 0, "tokens": 0, "time": 0}
        role_stats[role]["calls"] += 1
        role_stats[role]["tokens"] += m.get("tokens", 0)
        role_stats[role]["time"] += m.get("duration_sec", 0)

    msg = (
        "⚡ *Метрики производительности:*\n\n"
        f"📊 Вызовов: {total_calls}\n"
        f"🔢 Токенов: {total_tokens:,}\n"
        f"⏱ Общее время: {total_time:.1f}s\n"
        f"🚀 Средняя скорость: *{avg_toks:.1f} tok/s*\n"
        f"⏳ Средняя латенция: {avg_latency:.2f}s\n\n"
        "📋 *По ролям:*\n"
    )

    for role, stats in sorted(role_stats.items(), key=lambda x: x[1]["time"], reverse=True)[:10]:
        role_toks = stats["tokens"] / stats["time"] if stats["time"] > 0 else 0
        msg += f"  • `{role}`: {stats['calls']} calls, {role_toks:.1f} tok/s\n"

    try:
        await message.reply(msg, parse_mode="Markdown")
    except Exception:
        await message.reply(msg.replace("*", "").replace("`", ""))


async def cmd_openrouter_test(gateway, message: Message):
    """Quick OpenRouter connectivity test."""
    if message.from_user.id != gateway.admin_id:
        return

    or_cfg = gateway.config.get("system", {}).get("openrouter", {})
    if not or_cfg.get("enabled"):
        await message.reply("⚠️ OpenRouter не включён в конфиге.")
        return

    status_msg = await message.reply("🔄 Тестирую OpenRouter...")

    from src.openrouter_client import test_openrouter
    result = await test_openrouter(or_cfg.get("api_key", ""))

    if result["status"] == "ok":
        await status_msg.edit_text(
            f"✅ OpenRouter OK!\n"
            f"Модель: `{result['model']}`\n"
            f"Ответ: {result['response']}",
            parse_mode="Markdown",
        )
    else:
        await status_msg.edit_text(f"❌ OpenRouter ошибка: {result.get('error', 'unknown')}")
