"""Bot commands for RL training and status reporting."""

import json
import structlog
from aiogram.types import Message

logger = structlog.get_logger("BotCommands.Training")


async def cmd_train(gateway, message: Message):
    """Trigger one epoch of RL training (prompt evolution, benchmarks, optimization).

    Admin-only. Runs TrainingRunner.run_full_training(epochs=1) in background.
    """
    if message.from_user.id != gateway.admin_id:
        return

    status_msg = await message.reply(
        "🎯 *Запускаю RL Training Pipeline (1 эпоха)...*\n"
        "Prompt evolution → Benchmarks → Router optimization.\n"
        "Это может занять несколько минут.",
        parse_mode="Markdown",
    )

    try:
        from src.rl.training_loop import TrainingRunner
        import os

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        runner = TrainingRunner(api_key=api_key)
        result = await runner.run_full_training(epochs=1)

        report = runner.get_comparison_report()
        report_text = report[:3800] if report else "Отчёт недоступен."

        await status_msg.edit_text(
            f"✅ *RL Training завершён!*\n\n```\n{report_text}\n```",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("cmd_train failed", error=str(e))
        await status_msg.edit_text(
            f"❌ *Ошибка RL Training:*\n`{str(e)[:500]}`",
            parse_mode="Markdown",
        )


async def cmd_rl_status(gateway, message: Message):
    """Show RL subsystem status: reward model, experience buffer, goals, feedback."""
    if message.from_user.id != gateway.admin_id:
        return

    rl = getattr(gateway, "rl_orchestrator", None)
    if rl is None:
        await message.reply("⚠️ RL Orchestrator не инициализирован.", parse_mode="HTML")
        return

    try:
        status = rl.status()

        # Format readable summary
        buf = status.get("experience_buffer", {})
        fb = status.get("feedback", {})
        goals = status.get("goals", {})
        reward = status.get("reward_model", {})

        lines = [
            "🧠 <b>RL Subsystem Status</b>\n",
            f"📦 <b>Experience Buffer:</b>",
            f"  Total: {buf.get('total', 0)} | Successful: {buf.get('successful', 0)}",
            f"  Avg Reward: {buf.get('avg_reward', 0):.3f}",
            "",
            f"💬 <b>Feedback:</b>",
            f"  Total: {fb.get('total', 0)} | Corrections: {fb.get('corrections', 0)}",
            "",
            f"🎯 <b>Goals:</b>",
            f"  Active: {goals.get('by_status', {}).get('active', 0)}",
            f"  Completed: {goals.get('by_status', {}).get('completed', 0)}",
            "",
            f"📊 <b>Reward Model:</b>",
            f"  Episodes scored: {reward.get('episodes_scored', 0)}",
            f"  Avg reward: {reward.get('avg_reward', 0):.3f}",
        ]

        await message.reply("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error("cmd_rl_status failed", error=str(e))
        await message.reply(f"❌ Ошибка: {str(e)[:300]}", parse_mode="HTML")
