# Project: OpenClaw Factory

## Architecture

- **Core**: `/src` (System logic & engine)
- **External Bot**: `D:\Dmarket_bot` (Traded and developed by the factory)
- **Shared Packages**: `/packages` (e.g. Swabble)
- **Scripts**: `/scripts` (WSL, setup, and maintenance)

- **Skills**: `/workspace/skills` or `D:\Dmarket_bot\skills`

## Hardware Context (Grounded AI)
- **VRAM Management**: Due to the 16GB constraint, the system enforces **sequential model loading**. Heavy models (e.g., `arkady-reasoning-27b`) must be loaded one at a time with `keep_alive=0` to prevent OOM (Out of Memory) crashes.
- **Stability**: Attempting to load multiple large models simultaneously is considered a misuse of the system and may lead to instability.

## Command Rules
- Always run `openclaw daemon restart` after changing `.ts` files in `/src`.
- Use `openclaw config set` for configuration changes, do not edit JSON manually if possible.

- The system core is isolated from the bot products.

## Tooling & Execution
- **Manager Agent**: Use parallel Agent Manager (Command+E) in IDE to develop independent modules concurrently.
- **Workflows**: Run `/new_skill` workflow to generate boilerplate for new skills.
- **MCP**: Context7 enabled for latest `docs.openclaw.ai` reference.
