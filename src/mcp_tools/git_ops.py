"""
MCP Server: Read-Only Git Operations for OpenClaw Pipeline.

Exposes tools: git_status, git_log, git_diff, git_blame
so pipeline agents can inspect repository state without modification.

Security: Only read-only git sub-commands are allowed.
"""

import logging
import os
import subprocess
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("GitOpsMCP")
mcp = FastMCP("Git Operations")

_MAX_OUTPUT_CHARS = 16_000
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_git(args: list[str], cwd: str | None = None) -> str:
    """Run a git command safely. Returns stdout or error string."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or _REPO_ROOT,
        )
        output = result.stdout or result.stderr or "(no output)"
        return output[:_MAX_OUTPUT_CHARS]
    except subprocess.TimeoutExpired:
        return "Error: git command timed out (30s limit)"
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def git_status() -> str:
    """Show working tree status (git status --short)."""
    return _run_git(["status", "--short"])


@mcp.tool()
def git_log(count: int = 20, oneline: bool = True) -> str:
    """Show recent commit history.

    Args:
        count: Number of commits to show (max 100, default 20).
        oneline: Use one-line format (default True).
    """
    count = min(max(1, count), 100)
    args = ["log", f"-{count}"]
    if oneline:
        args.append("--oneline")
    return _run_git(args)


@mcp.tool()
def git_diff(staged: bool = False, file_path: str = "") -> str:
    """Show file changes (diff).

    Args:
        staged: If True, show staged changes (--cached). Default False.
        file_path: Optional specific file to diff.
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    if file_path:
        args.extend(["--", file_path])
    return _run_git(args)


@mcp.tool()
def git_blame(file_path: str) -> str:
    """Show per-line authorship for a file (git blame).

    Args:
        file_path: Path to file relative to repo root.
    """
    if not file_path:
        return "Error: file_path is required"
    return _run_git(["blame", "--", file_path])


if __name__ == "__main__":
    mcp.run()
