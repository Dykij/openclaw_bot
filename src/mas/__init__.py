"""
Multi-Agent System (MAS) — Autonomous agent orchestration for OpenClaw.

Provides:
- AgentOrchestrator: lifecycle management, task routing, autonomous loop
- AgentDefinition: declarative agent specs (role, model tier, tools)
- TaskRouter: routes incoming tasks to the best-fit agent
"""

from src.mas.orchestrator import AgentOrchestrator, AgentDefinition, AgentState

__all__ = ["AgentOrchestrator", "AgentDefinition", "AgentState"]
