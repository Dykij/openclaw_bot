"""
MCP Server: Read-Only Docker Operations for OpenClaw Pipeline.

Exposes tools: docker_ps, docker_compose_status, docker_logs
so pipeline agents can inspect container state without modification.

Security: Only read-only Docker sub-commands are allowed.
"""

import logging
import os
import subprocess
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("DockerOpsMCP")
mcp = FastMCP("Docker Operations")

_MAX_OUTPUT_CHARS = 16_000
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_cmd(args: list[str], cwd: str | None = None) -> str:
    """Run a command safely. Returns stdout or error string."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or _REPO_ROOT,
        )
        output = result.stdout or result.stderr or "(no output)"
        return output[:_MAX_OUTPUT_CHARS]
    except subprocess.TimeoutExpired:
        return "Error: command timed out (30s limit)"
    except FileNotFoundError:
        return f"Error: {args[0]} is not installed or not in PATH"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def docker_ps(all_containers: bool = False) -> str:
    """List running Docker containers.

    Args:
        all_containers: If True, show all containers including stopped ones.
    """
    args = ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]
    if all_containers:
        args.insert(2, "-a")
    return _run_cmd(args)


@mcp.tool()
def docker_compose_status() -> str:
    """Show docker compose service status."""
    return _run_cmd(["docker", "compose", "ps", "--format", "table"])


@mcp.tool()
def docker_logs(service: str, tail: int = 50) -> str:
    """Show recent logs for a docker compose service.

    Args:
        service: Name of the docker compose service.
        tail: Number of lines to show (max 500, default 50).
    """
    if not service:
        return "Error: service name is required"
    tail = min(max(1, tail), 500)
    return _run_cmd(["docker", "compose", "logs", "--tail", str(tail), service])


if __name__ == "__main__":
    mcp.run()
