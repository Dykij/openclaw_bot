"""
Pipeline JSON schemas, guardrail validators, and role-aware token budgets.

Extracted from pipeline_executor.py for modularity.
"""

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


ROLE_GUARDRAILS = {
    "Planner": validate_planner,
    "Auditor": validate_auditor,
}

GUARDRAIL_MAX_RETRIES = 2

# Role-aware max_tokens budgets
ROLE_TOKEN_BUDGET = {
    "Archivist": 1024, "State_Manager": 1024,
    "Latency_Optimizer": 1536, "Data_Analyst": 1536,
    "Executor_API": 2048, "Executor_Parser": 2048,
    "Executor_Logic": 2048, "Executor_Tools": 2048,
    "Executor_Architect": 2048, "Executor_Integration": 2048,
    "Risk_Analyst": 2048, "Debugger": 2048, "Test_Writer": 2048,
    "Planner": 3072, "Foreman": 3072,
    "Auditor": 2048,
}

# Roles eligible for MCP tool injection
TOOL_ELIGIBLE_ROLES = (
    "Executor_API", "Executor_Parser", "Executor_Tools",
    "Executor_Integration", "Executor_Architect",
    "Latency_Optimizer", "Debugger", "Test_Writer",
    "Planner", "Foreman",
)
