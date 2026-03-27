"""Tool / utility commands: tailscale, test, test_all_models, research."""

import asyncio

import aiohttp
import structlog
from aiogram.types import Message

logger = structlog.get_logger("GatewayCommands.Tools")


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


async def cmd_research(gateway, message: Message):
    """Deep Research: multi-step web search + memory synthesis."""
    if message.from_user.id != gateway.admin_id:
        return
    question = (message.text or "").replace("/research", "", 1).strip()
    if not question:
        await message.reply("Использование: `/research ваш вопрос`", parse_mode="Markdown")
        return

    status_msg = await message.reply("🔬 *Deep Research* запущен...", parse_mode="Markdown")

    async def update_status(role, model, text):
        try:
            escaped = gateway.archivist.escape_markdown(text)
            await status_msg.edit_text(f"🔬 *Deep Research*\n_{escaped}_", parse_mode="MarkdownV2")
        except Exception:
            pass

    try:
        from src.deep_research import DeepResearchPipeline

        router = gateway.config["system"]["model_router"]
        research_model = router.get("research", router.get("general", "meta-llama/llama-3.3-70b-instruct:free"))
        dr = DeepResearchPipeline(
            vllm_url=gateway.vllm_url,
            model=research_model,
            mcp_client=gateway.pipeline.openclaw_mcp,
        )
        result = await dr.research(question, status_callback=update_status)
        report = result["report"]
        sources_count = len(result.get("sources", []))
        iterations = result.get("iterations", 0)
        verified = result.get("verified_facts", [])
        refuted = result.get("refuted_facts", [])

        header = (
            f"🔬 *Deep Research* | Итерации: {iterations} | Источники: {sources_count}\n"
            f"✅ Подтверждено: {len(verified)} | ⚠️ Опровергнуто: {len(refuted)}\n\n"
        )
        try:
            await status_msg.edit_text(header + report, parse_mode="Markdown")
        except Exception:
            await status_msg.edit_text(
                f"🔬 Deep Research | Итерации: {iterations} | Источники: {sources_count}\n"
                f"✅ Подтверждено: {len(verified)} | ⚠️ Опровергнуто: {len(refuted)}\n\n{report}"
            )
    except Exception as e:
        logger.error("Deep Research failed", error=str(e))
        await status_msg.edit_text(f"❌ Deep Research ошибка: {e}")
