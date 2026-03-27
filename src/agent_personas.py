"""
Agent Persona Manager.

Loads persona markdown files from agents/ directory, provides persona
lookup by slug/role, and augments system prompts with persona context.

Based on the copilot/add-agents-module-structure branch design,
with fixes: YAML parsed via pyyaml, proper singleton pattern.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml
import structlog

logger = structlog.get_logger(__name__)

AGENTS_DIR = Path(__file__).parent.parent / "agents"


@dataclass
class AgentPersona:
    """Represents a single agent persona loaded from a markdown file."""
    slug: str
    name: str
    role: str
    category: str
    description: str
    system_prompt_addendum: str
    tags: List[str] = field(default_factory=list)
    file_path: str = ""


class AgentPersonaManager:
    """Singleton manager that loads and caches agent personas from agents/ directory."""

    _instance: Optional["AgentPersonaManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self, agents_dir: Optional[Path] = None):
        if self._loaded:
            return
        self._agents_dir = agents_dir or AGENTS_DIR
        self._personas: Dict[str, AgentPersona] = {}
        self._load_all()
        self._loaded = True

    def _load_all(self):
        """Scan agents/ subdirectories for *.md persona files."""
        if not self._agents_dir.is_dir():
            logger.warning(f"Agents directory not found: {self._agents_dir}")
            return

        for category_dir in sorted(self._agents_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            category = category_dir.name
            for md_file in sorted(category_dir.glob("*.md")):
                persona = self._parse_persona(md_file, category)
                if persona:
                    self._personas[persona.slug] = persona

        logger.info(f"Loaded {len(self._personas)} agent personas from {self._agents_dir}")

    def _parse_persona(self, path: Path, category: str) -> Optional[AgentPersona]:
        """Parse a persona markdown file with YAML frontmatter."""
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read persona file {path}: {e}")
            return None

        # Split YAML frontmatter from body
        if not text.startswith("---"):
            logger.warning(f"No YAML frontmatter in {path.name}, skipping")
            return None

        parts = text.split("---", 2)
        if len(parts) < 3:
            logger.warning(f"Malformed frontmatter in {path.name}")
            return None

        try:
            meta = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {path.name}: {e}")
            return None

        if not isinstance(meta, dict):
            return None

        body = parts[2].strip()
        slug = path.stem  # filename without .md

        return AgentPersona(
            slug=slug,
            name=meta.get("name", slug),
            role=meta.get("role", ""),
            category=category,
            description=meta.get("description", ""),
            system_prompt_addendum=body,
            tags=meta.get("tags", []),
            file_path=str(path),
        )

    def get(self, slug: str) -> Optional[AgentPersona]:
        """Get persona by slug."""
        return self._personas.get(slug)

    def list_all(self) -> List[AgentPersona]:
        """Return all loaded personas."""
        return list(self._personas.values())

    def list_by_category(self, category: str) -> List[AgentPersona]:
        """Return personas filtered by category."""
        return [p for p in self._personas.values() if p.category == category]

    def suggest_for_prompt(self, prompt: str) -> Optional[AgentPersona]:
        """Simple keyword-based persona suggestion for a user prompt."""
        lower = prompt.lower()
        best_score = 0
        best_persona = None

        for persona in self._personas.values():
            score = 0
            # Match tags
            for tag in persona.tags:
                if tag.lower() in lower:
                    score += 2
            # Match role name
            if persona.role.lower() in lower:
                score += 3
            # Match name
            if persona.name.lower() in lower:
                score += 5

            if score > best_score:
                best_score = score
                best_persona = persona

        return best_persona if best_score >= 2 else None

    def augment_system_prompt(self, base_prompt: str, persona: AgentPersona) -> str:
        """Append persona addendum to a system prompt."""
        if not persona.system_prompt_addendum:
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            f"[ACTIVE AGENT PERSONA: {persona.name} ({persona.role})]\n"
            f"{persona.system_prompt_addendum}\n"
            f"[END AGENT PERSONA]"
        )

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
