"""
Pipeline JSON schemas, guardrail validators, and role-aware token budgets.

Extracted from pipeline_executor.py for modularity.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Pydantic models for pipeline state validation
# ---------------------------------------------------------------------------

class PipelineStepResult(BaseModel):
    """Validated result of a single pipeline step."""
    role: str = Field(..., min_length=1)
    model: str = Field(default="unknown")
    response: str = Field(default="")
    duration_ms: int = Field(default=0, ge=0)

    @field_validator("response")
    @classmethod
    def response_not_empty_for_final(cls, v: str) -> str:
        # Allow empty for intermediate/parallel steps; final validation done at pipeline level
        return v.strip() if v else v


class PipelineResult(BaseModel):
    """Validated structure of a complete pipeline execution result."""
    final_response: str = Field(default="")
    brigade: str = Field(default="OpenClaw")
    chain_executed: List[str] = Field(default_factory=list)
    steps: List[PipelineStepResult] = Field(default_factory=list)
    status: str = Field(default="completed")
    question: Optional[str] = None
    duration_ms: int = Field(default=0, ge=0)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"completed", "ask_user", "create_offer", "error"}
        if v not in allowed:
            raise ValueError(f"Invalid pipeline status: {v!r}. Must be one of {allowed}")
        return v

# --- Structured Output JSON Schemas for pipeline roles ---
PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "List of plan steps"
        },
        "target_roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Roles to execute the plan"
        },
        "summary": {"type": "string", "description": "Brief summary of the plan"}
    },
    "required": ["plan", "summary"]
}

FOREMAN_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "instruction": {"type": "string"}
                },
                "required": ["role", "instruction"]
            },
            "minItems": 1
        },
        "priority": {"type": "string", "enum": ["high", "medium", "low"]}
    },
    "required": ["tasks"]
}

AUDITOR_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "partial"]},
        "issues": {
            "type": "array",
            "items": {"type": "string"}
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "summary": {"type": "string"}
    },
    "required": ["verdict", "summary"]
}

# Map role names to their structured output schemas (None = free-form text)
ROLE_SCHEMAS = {
    "Planner": PLANNER_SCHEMA,
    "Foreman": FOREMAN_SCHEMA,
    "Auditor": AUDITOR_SCHEMA,
}


# --- Guardrail validators per role ---
def validate_planner(response_text: str) -> tuple[bool, str]:
    """Validate Planner output has a usable plan."""
    lower = response_text.lower()
    if len(response_text.strip()) < 30:
        return False, "План слишком короткий. Расширь план минимум до 2 шагов."
    if not any(kw in lower for kw in ["план", "шаг", "plan", "step", "1.", "1)", "- "]):
        return False, "Ответ не содержит структурированного плана. Перепиши с нумерованными шагами."
    return True, ""


def validate_auditor(response_text: str) -> tuple[bool, str]:
    """Validate Auditor output has a verdict."""
    lower = response_text.lower()
    if not any(kw in lower for kw in ["pass", "fail", "partial", "✅", "❌", "ошибк", "верно", "корректн", "некорректн"]):
        return False, "Аудитор должен вынести вердикт: pass/fail/partial. Перепиши с чётким вердиктом."
    return True, ""


def validate_foreman(response_text: str) -> tuple[bool, str]:
    """Validate Foreman output has task assignments."""
    lower = response_text.lower()
    if len(response_text.strip()) < 20:
        return False, "Распределение задач слишком короткое. Укажи конкретные задачи для ролей."
    if not any(kw in lower for kw in ["task", "задач", "executor", "role", "роль", "instruction", "инструкци"]):
        return False, "Ответ не содержит распределения задач. Перепиши с явным назначением ролей."
    return True, ""


def validate_debugger(response_text: str) -> tuple[bool, str]:
    """Validate Debugger output is actionable."""
    lower = response_text.lower()
    if len(response_text.strip()) < 40:
        return False, "Отчёт отладчика слишком короткий. Добавь диагностику и предложения по исправлению."
    return True, ""


ROLE_GUARDRAILS = {
    "Planner": validate_planner,
    "Auditor": validate_auditor,
    "Foreman": validate_foreman,
    "Debugger": validate_debugger,
}

GUARDRAIL_MAX_RETRIES = 2

# Role-aware max_tokens budgets
ROLE_TOKEN_BUDGET = {
    "Archivist": 768, "State_Manager": 1536,
    "Latency_Optimizer": 1536, "Data_Analyst": 1536,
    "Executor_API": 2048, "Executor_Parser": 2048,
    "Executor_Logic": 2048, "Executor_Tools": 2048,
    "Executor_Architect": 2048, "Executor_Integration": 2048,
    "Risk_Analyst": 1536, "Debugger": 2048, "Test_Writer": 2560,
    "Planner": 2048, "Foreman": 2048,
    "Auditor": 1536,
}

# Roles eligible for MCP tool injection
TOOL_ELIGIBLE_ROLES = (
    "Executor_API", "Executor_Parser", "Executor_Tools",
    "Executor_Integration", "Executor_Architect",
    "Latency_Optimizer", "Debugger", "Test_Writer",
    "Planner", "Foreman",
    "Data_Analyst", "Risk_Analyst",
)
