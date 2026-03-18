"""
Pipeline utility functions: text cleaning, context compression,
prompt building, and chain grouping.

Extracted from pipeline_executor.py for modularity.
"""

import os
import re

import structlog

logger = structlog.get_logger(__name__)


def group_chain(chain_list: list[str]) -> list[tuple[str, ...]]:
    """Groups consecutive Executor_ roles into tuples for parallel dispatch."""
    groups = []
    executor_batch = []
    for role in chain_list:
        if role.startswith("Executor_"):
            executor_batch.append(role)
        else:
            if executor_batch:
                groups.append(tuple(executor_batch))
                executor_batch = []
            groups.append((role,))
    if executor_batch:
        groups.append(tuple(executor_batch))
    return groups


def clean_response_for_user(text: str) -> str:
    """Strip internal STAR markup, <think> blocks, MCP artifacts, and process confidence tags."""
    # Remove <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove STAR labels (SITUATION:, TASK:, ACTION:, RESULT: at line start)
    text = re.sub(r"^\s*(SITUATION|TASK|ACTION|RESULT)\s*:\s*", "", text, flags=re.MULTILINE)
    # Remove [MCP ...], [Proof of Work ...], [Correction], [PIPELINE CONTEXT ...] blocks
    text = re.sub(r"\[MCP[^\]]*\]:?[^\n]*\n?", "", text)
    text = re.sub(r"\[Proof of Work[^\]]*\]:?[^\n]*\n?", "", text)
    text = re.sub(r"\[Correction\]:?\s*", "", text)
    text = re.sub(r"\[PIPELINE CONTEXT[^\]]*\][^\n]*\n?", "", text)
    # Remove [AGENT PROTOCOL...] remnants
    text = re.sub(r"\[AGENT PROTOCOL[^\]]*\][^\n]*\n?", "", text)
    # Remove [ARCHIVIST PROTOCOL...] remnants
    text = re.sub(r"\[ARCHIVIST PROTOCOL[^\]]*\][^\n]*\n?", "", text)
    # Remove [EXECUTOR PROTOCOL...] remnants
    text = re.sub(r"\[EXECUTOR PROTOCOL[^\]]*\][^\n]*\n?", "", text)
    # Remove [RAG_CONFIDENCE: ...] tags (used internally by memory search)
    text = re.sub(r"\[RAG_CONFIDENCE:\s*\w+\]\s*", "", text)
    # Remove stray JSON tool-call artifacts outside code blocks
    text = re.sub(r'(?<!`)\{"name"\s*:.*?"arguments"\s*:.*?\}(?!`)', '', text, flags=re.DOTALL)
    # Remove repeated consecutive paragraphs (dedup)
    paragraphs = text.split('\n\n')
    seen = set()
    deduped = []
    for p in paragraphs:
        p_key = p.strip().lower()
        if p_key and p_key not in seen:
            seen.add(p_key)
            deduped.append(p)
        elif not p_key:
            deduped.append(p)
    text = '\n\n'.join(deduped)
    # Process confidence tag: [УВЕРЕННОСТЬ: X/10]
    confidence_match = re.search(r'\[УВЕРЕННОСТЬ:\s*(\d+)/10\]', text)
    if confidence_match:
        score = int(confidence_match.group(1))
        text = re.sub(r'\s*\[УВЕРЕННОСТЬ:\s*\d+/10\]\s*', '', text)
        if score < 7:
            text = '⚠️ Ответ может содержать неточности — данные частично не подтверждены.\n\n' + text
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compress_for_next_step(role_name: str, response: str) -> str:
    """
    Smart context compression: preserves JSON blocks, MCP results,
    and respects sentence boundaries instead of blind truncation.
    """
    # 1. Extract and preserve JSON code blocks (instructions for Executor)
    json_blocks = re.findall(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    json_section = ""
    if json_blocks:
        json_section = "\n```json\n" + json_blocks[0][:800] + "\n```"

    # 2. Extract MCP execution results
    mcp_results = re.findall(r'\[MCP Execution Result\]:\n(.*?)(?:\n\n|\Z)', response, re.DOTALL)
    mcp_section = ""
    if mcp_results:
        mcp_section = "\n[MCP Result]: " + mcp_results[0][:500]

    # 3. Clean text: remove <think>, STAR labels, code blocks, MCP markers
    clean = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    clean = re.sub(r'```json.*?```', '', clean, flags=re.DOTALL)
    clean = re.sub(r'\[MCP[^\]]*\].*?\n', '', clean)
    clean = re.sub(r'\[Proof of Work[^\]]*\].*?\n', '', clean)
    clean = re.sub(r'\n{2,}', '\n', clean).strip()

    # 4. Smart truncation: up to 1500 chars, respecting sentence boundaries
    max_chars = 1500
    if len(clean) > max_chars:
        cut = clean[:max_chars]
        last_boundary = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '), cut.rfind('\n'))
        if last_boundary > max_chars // 2:
            cut = cut[:last_boundary + 1]
        clean = cut + "..."

    return f"[{role_name} Output]: {clean}{json_section}{mcp_section}"


def emergency_compress(step_prompt: str, ctx_threshold: int, role_name: str) -> str:
    """
    Emergency context compression when input exceeds ctx budget.
    Preserves structure: keeps [ORIGINAL USER TASK] and compresses [PIPELINE CONTEXT].
    """
    parts = step_prompt.split("[ORIGINAL USER TASK]")
    if len(parts) < 2:
        target_chars = ctx_threshold * 4
        if len(step_prompt) > target_chars:
            cut = step_prompt[:target_chars]
            last_boundary = max(cut.rfind('. '), cut.rfind('\n'), cut.rfind('? '))
            if last_boundary > target_chars // 2:
                cut = cut[:last_boundary + 1]
            return cut + "\n[...CONTEXT COMPRESSED DUE TO OVERFLOW...]"
        return step_prompt

    pipeline_ctx = parts[0]
    original_task = "[ORIGINAL USER TASK]" + parts[1]

    available_for_ctx = (ctx_threshold * 4) - len(original_task)

    if available_for_ctx < 400:
        logger.warning(f"Extreme overflow for {role_name}: dropping pipeline context entirely")
        return (
            "[PIPELINE CONTEXT — COMPRESSED]\n"
            "Previous steps completed. Details truncated due to context limit.\n\n"
            + original_task
        )

    # Aggressive compression of pipeline context
    clean_ctx = re.sub(r'<think>.*?</think>', '', pipeline_ctx, flags=re.DOTALL)
    clean_ctx = re.sub(r'```json.*?```', '[JSON_BLOCK]', clean_ctx, flags=re.DOTALL)
    clean_ctx = re.sub(r'\n{2,}', '\n', clean_ctx).strip()

    if len(clean_ctx) > available_for_ctx:
        head_size = min(400, available_for_ctx // 3)
        tail_size = available_for_ctx - head_size - 60
        head = clean_ctx[:head_size]
        tail = clean_ctx[-tail_size:] if tail_size > 0 else ""
        head_boundary = max(head.rfind('. '), head.rfind('\n'))
        if head_boundary > head_size // 2:
            head = head[:head_boundary + 1]
        tail_start = tail.find('. ')
        if tail_start > 0 and tail_start < len(tail) // 3:
            tail = tail[tail_start + 2:]
        clean_ctx = head + "\n[...COMPRESSED...]\n" + tail

    logger.info(f"Context compressed for {role_name}: {len(pipeline_ctx)} → {len(clean_ctx)} chars")
    return clean_ctx + "\n\n" + original_task


def sanitize_file_content(content: str) -> str:
    """Strip potential prompt injection markers from file content before prompt injection."""
    content = re.sub(r'(?i)\[?(system|user|assistant)\s*(prompt|message|role)\]?\s*:', '', content)
    content = re.sub(r'(?i)(ignore previous instructions|forget your instructions|new instructions:)', '[FILTERED]', content)
    content = re.sub(r'<\|im_(start|end)\|>', '', content)
    return content


def build_role_prompt(role_name: str, role_config: dict, framework_root: str, task_type: str = None) -> str:
    """Build the system prompt for a given pipeline role with protocol injections."""
    if task_type:
        return (
            "Ты — универсальный ИИ-ассистент OpenClaw. Отвечай на вопрос пользователя "
            "кратко (2-5 предложений), точно и на РУССКОМ ЯЗЫКЕ.\n"
            "Если вопрос простой (математика, факт, определение) — давай прямой ответ без рассуждений.\n"
            "НЕ используй служебные метки (STAR, SITUATION и т.д.). НЕ описывай свои возможности."
        )

    system_prompt = role_config.get("system_prompt", "You are an AI assistant.")

    is_planner = "Planner" in role_name or "Orchestrator" in role_name or "Foreman" in role_name
    is_archivist = "Archivist" in role_name

    if is_archivist:
        system_prompt += (
            "\n\n[ARCHIVIST PROTOCOL: CRITIC + FORMATTER]"
            "\nТы получаешь технический вывод от предыдущего агента."
            "\nТвоя задача — ВЕРИФИЦИРОВАТЬ и ПЕРЕПИСАТЬ его в чистый, человекочитаемый формат."
            "\n"
            "\nФАЗА 1 — ВЕРИФИКАЦИЯ (Скептический критик):"
            "\n- Проверь ответ на ВНУТРЕННИЕ ПРОТИВОРЕЧИЯ (одно утверждение опровергает другое)."
            "\n- Проверь на ФАБРИКАЦИИ: конкретные цифры, даты, имена — есть ли основания в контексте?"
            "\n- Проверь на TOOL BYPASS: если агент описывает 'я бы выполнил команду...' вместо реального результата — отметь как непроверенное."
            "\n- Если факт НЕ подкреплён данными из контекста, УДАЛИ его, а не передавай пользователю."
            "\n"
            "\nФАЗА 2 — ФОРМАТИРОВАНИЕ:"
            "\n- Удали ВСЮ служебную разметку: SITUATION, TASK, ACTION, RESULT, <think> блоки, [MCP...], [Proof of Work...]."
            "\n- НЕ добавляй вступлений ('Давайте рассмотрим...', 'Представляет собой...')."
            "\n- Каждое предложение = конкретный ВЕРИФИЦИРОВАННЫЙ факт или вывод."
            "\n- Пиши на РУССКОМ ЯЗЫКЕ."
            "\n- Формат: прямой ответ на вопрос пользователя, без мета-комментариев."
            "\n"
            "\nФАЗА 3 — ОЦЕНКА УВЕРЕННОСТИ:"
            "\n- В САМОМ КОНЦЕ ответа добавь тег: [УВЕРЕННОСТЬ: X/10]"
            "\n  где X — твоя оценка достоверности финального ответа (10 = абсолютно уверен, подтверждено данными; 1 = полная догадка)."
            "\n- Если X < 7, ПЕРЕД основным ответом добавь: '⚠️ Ответ может содержать неточности — данные частично не подтверждены.'"
            "\n- Оценивай честно: непроверенные факты = низкая оценка."
        )
    elif is_planner:
        os_name = "Windows" if os.name == "nt" else "Linux"
        system_prompt += (
            "\n\n[AGENT PROTOCOL: STAR-STRATEGY — INTERNAL ONLY]"
            "\n1. Memory Bank: Use .memory-bank for persistence."
            "\n2. Tooling: Если для ответа нужны данные из файловой системы, НЕМЕДЛЕННО вызывай доступные инструменты (list_directory, read_file). НЕ описывай, что ты хочешь вызвать — ВЫЗЫВАЙ."
            "\n3. STAR используй ТОЛЬКО внутри тегов <think>...</think> для структурирования рассуждений."
            "\n4. Финальный ответ (вне <think>) должен быть ЧИСТЫМ текстом для пользователя:"
            "\n   - БЕЗ меток SITUATION/TASK/ACTION/RESULT"
            "\n   - БЕЗ повторения одних и тех же фактов в разных формулировках"
            "\n   - Каждое предложение = новый факт или конкретное действие"
            "\n   - Если задача требует инструментов и ты сгенерировал JSON — добавь его в ```json``` блок"
            "\n5. ЗАПРЕЩЁННЫЕ конструкции: 'Представляет собой...', 'Является эффективной...', 'Для конкретных рекомендаций необходимо...'"
            "\n6. SCOPE LIMITATION: Объясняй только четко установленные факты из контекста и доступных данных. Если ты НЕ УВЕРЕН — скажи 'недостаточно данных' вместо домысливания. Пропускай спорные или непроверенные области."
            "\n7. ВАЖНО: Весь ответ на РУССКОМ ЯЗЫКЕ."
            f"\n8. СИСТЕМНАЯ СРЕДА: Бот работает на {os_name}. Инструменты доступны через MCP. НЕ предлагай прямые shell-команды (grep, tree, cat) — вызывай MCP-инструменты: list_directory, read_file, search_memory."
        )

        # Inject BRAIN.md for Planners
        brain_path = os.path.join(framework_root, "BRAIN.md")
        if os.path.exists(brain_path):
            try:
                with open(brain_path, "r", encoding="utf-8") as f:
                    brain_content = f.read()
                brain_content = sanitize_file_content(brain_content)
                system_prompt += f"\n\n[LATEST BRAIN.md CONTEXT]\n{brain_content}"
            except Exception as e:
                logger.warning(f"Failed to read BRAIN.md: {e}")
    else:
        # Executors and other roles: minimal protocol
        system_prompt += (
            "\n\n[EXECUTOR PROTOCOL]"
            "\nВыполняй задачу точно по инструкции. Результат — только JSON или код."
            "\nНикаких пояснений, вступлений, заключений."
            "\nЯзык ответа: РУССКИЙ."
        )

    return system_prompt
