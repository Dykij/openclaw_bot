"""
ClawHub integration — connector for OpenClaw Bot to the ClawHub platform.

Provides:
- ClawHubClient: API connector with authentication
- Task sync: pull tasks from ClawHub, push results back
- Skill registry: register bot capabilities with ClawHub
"""

from src.clawhub.client import ClawHubClient

__all__ = ["ClawHubClient"]
