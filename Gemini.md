# Project: OpenClaw Factory

## Architecture
- **Core**: /src/core (System logic)
- **Workspace**: /workspace (User data & specific bot configs)
- **Skills**: /workspace/skills (Python/TS tools)

## Command Rules
- Always run `openclaw daemon restart` after changing .ts files in /src.
- Use `openclaw config set` for configuration changes, do not edit JSON manually if possible.
- Agents like `Dmarket_bot` or `Arkay Bot` live in their respective subdirectories inside `/workspace` or mounted drives and should be developed concurrently.

## Tooling & Execution
- **Manager Agent**: Use parallel Agent Manager (Command+E) in IDE to develop independent modules concurrently (e.g. trading bot logic and Telegram notifications).
- **Workflows**: Run `/new_skill` workflow to automatically generate boilerplate for new skills.
- **MCP**: Context7 enabled for latest `docs.openclaw.ai` reference.
