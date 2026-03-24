"""
Agent Persona System for OpenClaw Bot.

Loads and manages curated agent personas from Markdown files in the
``agents/`` directory at the repository root.  Each persona is a plain
Markdown file with YAML frontmatter that describes a specialised role.

Public API
----------
AgentPersonaManager  — singleton that loads all personas and keeps track
                       of the currently active persona per chat session.
build_persona_prompt(persona) — returns a system-prompt augmentation string
                               that can be prepended to any role prompt.
route_to_persona(message)    — keyword-based auto-routing suggestion.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class AgentPersona:
    """A single agent persona loaded from a Markdown file."""

    name: str
    slug: str                   # URL-safe, lower-kebab identifier
    division: str
    tags: List[str]
    description: str
    body: str                   # Full Markdown body (Role/Process/Artifacts/Metrics)
    filepath: str


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)",
    re.DOTALL,
)
_YAML_FIELD_RE = re.compile(r'^(?P<key>\w[\w-]*):\s*(?P<val>.+)$', re.MULTILINE)
_YAML_LIST_RE = re.compile(r'"([^"]+)"')


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from Markdown body. Returns (meta, body)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    fm_text = m.group("fm")
    body = m.group("body")
    meta: dict = {}

    for line in fm_text.splitlines():
        fm = _YAML_FIELD_RE.match(line.strip())
        if not fm:
            continue
        key = fm.group("key")
        val = fm.group("val").strip()

        # Quoted string
        if val.startswith('"') and val.endswith('"'):
            meta[key] = val[1:-1]
        # Inline list  ["a", "b", "c"]
        elif val.startswith("["):
            meta[key] = _YAML_LIST_RE.findall(val)
        else:
            meta[key] = val

    return meta, body


def load_persona_from_file(filepath: str) -> Optional[AgentPersona]:
    """Parse a single persona Markdown file and return an AgentPersona."""
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        logger.warning("Cannot read persona file %s: %s", filepath, exc)
        return None

    meta, body = _parse_frontmatter(text)
    if not meta.get("name"):
        logger.warning("Skipping %s — missing 'name' in frontmatter", filepath)
        return None

    raw_name: str = meta["name"]
    slug = raw_name.lower().replace(" ", "-").replace("_", "-")
    # Strip non-alphanumeric (except hyphen) and normalize consecutive hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    return AgentPersona(
        name=raw_name,
        slug=slug,
        division=str(meta.get("division", "general")).lower(),
        tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
        description=str(meta.get("description", "")),
        body=body.strip(),
        filepath=filepath,
    )


def load_all_personas(agents_dir: str) -> List[AgentPersona]:
    """Walk ``agents_dir`` recursively and load all ``.md`` files."""
    personas: List[AgentPersona] = []
    if not os.path.isdir(agents_dir):
        logger.warning("Agents directory not found: %s", agents_dir)
        return personas

    for root, _dirs, files in os.walk(agents_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fp = os.path.join(root, fname)
            persona = load_persona_from_file(fp)
            if persona:
                personas.append(persona)
                logger.debug("Loaded persona '%s' from %s", persona.name, fp)

    logger.info("Loaded %d agent personas from %s", len(personas), agents_dir)
    return personas


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Indexes personas by slug, name, and division for fast lookup."""

    def __init__(self, personas: List[AgentPersona]) -> None:
        self._by_slug: Dict[str, AgentPersona] = {}
        self._by_division: Dict[str, List[AgentPersona]] = {}

        for p in personas:
            self._by_slug[p.slug] = p
            # Also allow lookup by bare filename stem (secondary alias)
            stem = os.path.splitext(os.path.basename(p.filepath))[0]
            if stem != p.slug:
                if stem in self._by_slug:
                    logger.debug(
                        "Stem collision for '%s' (already mapped to '%s'); slug lookup preferred",
                        stem, self._by_slug[stem].slug,
                    )
                else:
                    self._by_slug[stem] = p
            self._by_division.setdefault(p.division, []).append(p)

    # ------------------------------------------------------------------
    def get(self, slug: str) -> Optional[AgentPersona]:
        """Look up a persona by slug or file stem (case-insensitive)."""
        return self._by_slug.get(slug.lower())

    def list_all(self) -> List[AgentPersona]:
        return list(self._by_slug.values())

    def list_unique(self) -> List[AgentPersona]:
        """Return deduplicated list (one entry per unique slug/name pair)."""
        seen: set = set()
        result: List[AgentPersona] = []
        for p in self._by_slug.values():
            if p.slug not in seen:
                seen.add(p.slug)
                result.append(p)
        return sorted(result, key=lambda x: (x.division, x.name))

    def list_by_division(self, division: str) -> List[AgentPersona]:
        return self._by_division.get(division.lower(), [])

    def divisions(self) -> List[str]:
        return sorted(self._by_division.keys())


# ---------------------------------------------------------------------------
# Router — simple keyword-based intent matching
# ---------------------------------------------------------------------------

_ROUTING_RULES: List[tuple[List[str], str]] = [
    # (keywords, slug)
    (["review", "code review", "проверь код", "ревью"], "code-reviewer"),
    (["test", "testing", "qa", "тест", "написать тесты", "автотест"], "qa-specialist"),
    (["deploy", "ci/cd", "docker", "kubernetes", "pipeline", "деплой", "инфраструктур"], "devops-automator"),
    (["security", "vulnerability", "безопасность", "уязвимость", "injection", "сканировани"], "security-engineer"),
    (["architecture", "architect", "design system", "архитектура", "system design"], "backend-architect"),
    (["ai", "llm", "machine learning", "model", "vllm", "fine-tuning", "обучение модел"], "ai-engineer"),
    (["ux", "user experience", "usability", "user flow", "wireframe", "ux-аудит"], "ux-architect"),
    (["ui", "interface", "css", "design token", "component", "интерфейс"], "ui-designer"),
    (["image", "prompt", "stable diffusion", "midjourney", "dalle", "изображени"], "image-prompt-engineer"),
    (["product", "prd", "roadmap", "feature", "user story", "продукт", "roadmap"], "product-manager"),
    (["strategy", "market", "competitive", "positioning", "стратеги", "рынок"], "product-strategist"),
    (["seo", "search", "keyword", "organic", "сео", "поисков"], "seo-specialist"),
    (["content", "copy", "editorial", "blog", "контент", "статья", "текст"], "content-strategist"),
    (["support", "troubleshoot", "debug issue", "bug report", "саппорт", "проблема"], "technical-support"),
    (["sprint", "project", "backlog", "stakeholder", "спринт", "проект", "планировани"], "project-manager"),
    (["senior", "code", "python", "typescript", "refactor", "рефактор", "код"], "senior-developer"),
]


def route_to_persona(message: str, registry: AgentRegistry) -> Optional[AgentPersona]:
    """
    Keyword-based routing: scan the user message and return the best-fit
    persona, or None if no confident match is found.
    """
    lower = message.lower()
    scores: Dict[str, int] = {}

    for keywords, slug in _ROUTING_RULES:
        for kw in keywords:
            if kw in lower:
                scores[slug] = scores.get(slug, 0) + 1

    if not scores:
        return None

    best_slug = max(scores, key=lambda s: scores[s])
    return registry.get(best_slug)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_persona_prompt(persona: AgentPersona) -> str:
    """
    Build a system-prompt augmentation string for the given persona.
    This is prepended to (not replacing) the base system prompt.
    """
    return (
        f"[ACTIVE AGENT PERSONA: {persona.name.upper()} | {persona.division.upper()} DIVISION]\n"
        f"Description: {persona.description}\n\n"
        f"{persona.body}\n\n"
        "[END AGENT PERSONA]\n"
        "Apply the role, process, and quality metrics above to your response. "
        "Produce the corresponding artifacts where applicable."
    )


# ---------------------------------------------------------------------------
# Manager — stateful singleton (one active persona per chat_id)
# ---------------------------------------------------------------------------

class AgentPersonaManager:
    """
    Singleton-style manager.  Holds the registry and tracks which persona
    (if any) is active per Telegram chat_id.
    """

    def __init__(self, agents_dir: Optional[str] = None) -> None:
        if agents_dir is None:
            # Resolve relative to repo root (two levels up from src/)
            src_dir = os.path.dirname(__file__)
            agents_dir = os.path.join(src_dir, "..", "agents")
        agents_dir = os.path.abspath(agents_dir)

        personas = load_all_personas(agents_dir)
        self.registry = AgentRegistry(personas)
        self._active: Dict[int, AgentPersona] = {}   # chat_id → persona

    # ------------------------------------------------------------------
    # Persona activation / deactivation
    # ------------------------------------------------------------------

    def activate(self, chat_id: int, slug: str) -> Optional[AgentPersona]:
        """
        Activate a persona for a chat.  Returns the persona on success,
        None if the slug is not found.
        """
        persona = self.registry.get(slug)
        if persona:
            self._active[chat_id] = persona
        return persona

    def deactivate(self, chat_id: int) -> None:
        self._active.pop(chat_id, None)

    def active_persona(self, chat_id: int) -> Optional[AgentPersona]:
        return self._active.get(chat_id)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_persona_augmentation(self, chat_id: int) -> str:
        """
        Return the system-prompt augmentation for the active persona, or an
        empty string if no persona is active for the chat.
        """
        persona = self.active_persona(chat_id)
        if persona:
            return build_persona_prompt(persona)
        return ""

    def suggest_persona(self, message: str) -> Optional[AgentPersona]:
        """Auto-route suggestion based on message keywords (does not activate)."""
        return route_to_persona(message, self.registry)

    # ------------------------------------------------------------------
    # Formatting helpers for Telegram output
    # ------------------------------------------------------------------

    def format_list(self) -> str:
        """Return a formatted list of all available personas for Telegram."""
        personas = self.registry.list_unique()
        if not personas:
            return "⚠️ Нет доступных агентов."

        lines = ["🤖 *Доступные агенты:*\n"]
        current_div = None
        div_icons = {
            "engineering": "🔧",
            "design": "🎨",
            "product": "📦",
            "testing": "🧪",
            "marketing": "📣",
            "support": "🎧",
            "project-management": "📋",
        }
        for p in personas:
            if p.division != current_div:
                current_div = p.division
                icon = div_icons.get(p.division, "📁")
                lines.append(f"\n{icon} *{p.division.title()}*")
            lines.append(f"  • `{p.slug}` — {p.description}")

        lines.append("\nИспользование: `/agent <slug>` чтобы активировать")
        return "\n".join(lines)

    def format_info(self, slug: str) -> str:
        """Return detailed info about a persona for Telegram."""
        persona = self.registry.get(slug)
        if not persona:
            return f"❌ Агент `{slug}` не найден. Используй `/agents` для списка."
        tags_str = ", ".join(f"`{t}`" for t in persona.tags)
        return (
            f"*{persona.name}*\n"
            f"Дивизион: `{persona.division}`\n"
            f"Теги: {tags_str}\n\n"
            f"{persona.description}\n\n"
            f"_Активировать:_ `/agent {persona.slug}`"
        )
