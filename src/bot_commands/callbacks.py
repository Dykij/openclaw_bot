"""Callback query and unknown command handlers."""

import structlog
from aiogram.types import CallbackQuery, Message

from src.bot_commands.status import cmd_status, cmd_models
from src.bot_commands.diagnostics import cmd_test, cmd_history, cmd_perf

logger = structlog.get_logger("BotCommands.Callbacks")


async def handle_callback_query(gateway, callback: CallbackQuery):
    """Handle inline button presses."""
    if callback.from_user.id != gateway.admin_id:
        await callback.answer("⛔ Access Denied.")
        return

    action = callback.data
    if action == "cmd_status":
        await cmd_status(gateway, callback.message, from_callback=True)
        await callback.answer()
    elif action == "cmd_models":
        await cmd_models(gateway, callback.message, from_callback=True)
        await callback.answer()
    elif action == "cmd_test":
        await callback.answer("Запускаю VRAM тест...")
        await cmd_test(gateway, callback.message)
    elif action == "cmd_history":
        await cmd_history(gateway, callback.message)
        await callback.answer()
    elif action == "cmd_perf":
        await cmd_perf(gateway, callback.message)
        await callback.answer()
    else:
        await callback.answer()


async def handle_unknown_command(gateway, message: Message):
    """Ignore or warn about unknown Telegram menu commands."""
    if message.from_user.id != gateway.admin_id:
        return
    await message.reply("⚠️ Неизвестная команда. Если это кнопка из меню, убедитесь, что она реализована.")
