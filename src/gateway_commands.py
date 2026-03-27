"""Backward-compatible facade — real implementations live in src/handlers/commands/."""

from src.handlers.commands import (  # noqa: F401
    cmd_agent,
    cmd_agents,
    cmd_help,
    cmd_history,
    cmd_models,
    cmd_openrouter_test,
    cmd_perf,
    cmd_research,
    cmd_start,
    cmd_status,
    cmd_tailscale,
    cmd_test,
    cmd_test_all_models,
    handle_callback_query,
    handle_document,
    handle_photo,
    handle_unknown_command,
    handle_voice,
)
