"""Obsidian Vault Bridge — bidirectional read/write/search for OpenClaw Bot.

Provides:
- Read/write/search Obsidian vault markdown files
- Create research notes with backlinks
- Build knowledge graph from vault links
- Persist research results and learning logs
- Search vault via full-text and backlink graph

This replaces the one-way vault_to_training.py export with a full
bidirectional bridge, enabling the self-learning loop:
  pipeline results → vault notes → graph-RAG → context for next pipeline run

v1 (2026-04-06): Initial implementation.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger("ObsidianBridge")

# Default vault location (configurable)
_DEFAULT_VAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".obsidian"
)


@dataclass
class VaultNote:
    """Represents a single Obsidian vault note."""

    path: str  # relative path within vault
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)  # [[link]] targets
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    modified: float = 0.0


@dataclass
class KnowledgeGraphNode:
    """Node in the vault knowledge graph."""

    note_path: str
    title: str
    links_to: List[str] = field(default_factory=list)
    linked_from: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    degree: int = 0  # total connections


class ObsidianBridge:
    """Bidirectional bridge between OpenClaw bot and Obsidian vault.

    Usage:
        bridge = ObsidianBridge("/path/to/vault")
        # Write research results
        bridge.save_research_note("AI Agents 2026", report, sources, tags=["research"])
        # Search vault
        results = bridge.search("multi-agent orchestration")
        # Get knowledge graph
        graph = bridge.build_knowledge_graph()
        # Save learning log
        bridge.save_learning_log(task="research", outcome="success", lessons=["..."])
    """

    def __init__(self, vault_path: str | None = None):
        self.vault_path = Path(vault_path or _DEFAULT_VAULT_PATH)
        self._ensure_vault_structure()
        logger.info("ObsidianBridge initialized", vault_path=str(self.vault_path))

    def _ensure_vault_structure(self) -> None:
        """Create standard vault subdirectories if they don't exist."""
        dirs = [
            "Research",
            "Research/Reports",
            "Research/Sources",
            "Learning",
            "Learning/Logs",
            "Learning/Skills",
            "Knowledge",
            "Knowledge/Concepts",
            "Knowledge/Agents",
            "Pipeline",
            "Pipeline/Tasks",
            "Pipeline/Sessions",
        ]
        for d in dirs:
            (self.vault_path / d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_note(self, relative_path: str) -> Optional[VaultNote]:
        """Read a single note from the vault."""
        fpath = self.vault_path / relative_path
        if not fpath.exists() or not fpath.suffix == ".md":
            return None
        try:
            content = fpath.read_text(encoding="utf-8")
            return self._parse_note(relative_path, content)
        except Exception as e:
            logger.warning("Failed to read note", path=relative_path, error=str(e))
            return None

    def list_notes(self, subfolder: str = "", tags: List[str] | None = None) -> List[VaultNote]:
        """List all notes in a subfolder, optionally filtered by tags."""
        base = self.vault_path / subfolder if subfolder else self.vault_path
        if not base.exists():
            return []

        notes: List[VaultNote] = []
        for fpath in base.rglob("*.md"):
            try:
                content = fpath.read_text(encoding="utf-8")
                rel = str(fpath.relative_to(self.vault_path))
                note = self._parse_note(rel, content)
                if tags and not any(t in note.tags for t in tags):
                    continue
                notes.append(note)
            except Exception:
                continue
        return notes

    def _parse_note(self, relative_path: str, content: str) -> VaultNote:
        """Parse a markdown note into a VaultNote dataclass."""
        # Extract frontmatter (YAML between --- lines)
        frontmatter: Dict[str, Any] = {}
        body = content
        fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            body = content[fm_match.end():]
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    frontmatter[key.strip()] = val.strip()

        # Extract tags (#tag)
        tags = re.findall(r"#(\w[\w/-]*)", content)

        # Extract backlinks ([[link]])
        backlinks = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", content)

        # Extract title from first H1 or filename
        title_match = re.match(r"^#\s+(.+)", body)
        title = title_match.group(1) if title_match else Path(relative_path).stem

        fpath = self.vault_path / relative_path
        try:
            modified = fpath.stat().st_mtime
        except (FileNotFoundError, OSError):
            modified = 0.0

        return VaultNote(
            path=relative_path,
            title=title,
            content=body.strip(),
            tags=list(set(tags)),
            backlinks=list(set(backlinks)),
            frontmatter=frontmatter,
            modified=modified,
        )

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def save_note(
        self,
        relative_path: str,
        content: str,
        frontmatter: Dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> str:
        """Write a markdown note to the vault.

        Returns the absolute path of the written file.
        """
        fpath = self.vault_path / relative_path
        if fpath.exists() and not overwrite:
            # Append timestamp to avoid collisions
            stem = fpath.stem
            suffix = fpath.suffix
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fpath = fpath.parent / f"{stem}_{ts}{suffix}"

        fpath.parent.mkdir(parents=True, exist_ok=True)

        # Build frontmatter
        fm_text = ""
        if frontmatter:
            lines = ["---"]
            for k, v in frontmatter.items():
                if isinstance(v, list):
                    lines.append(f"{k}:")
                    for item in v:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"{k}: {v}")
            lines.append("---\n")
            fm_text = "\n".join(lines)

        fpath.write_text(fm_text + content, encoding="utf-8")
        logger.info("Note saved", path=str(fpath.relative_to(self.vault_path)))
        return str(fpath)

    def save_research_note(
        self,
        title: str,
        report: str,
        sources: List[str],
        tags: List[str] | None = None,
        confidence: float = 0.0,
        evidence_count: int = 0,
        quality_metrics: Dict[str, Any] | None = None,
    ) -> str:
        """Save a deep research result as a structured Obsidian note.

        Creates backlinks to source notes and tags for navigation.
        """
        all_tags = ["research", "auto-generated"] + (tags or [])
        ts = datetime.now(timezone.utc)
        slug = re.sub(r"[^\w\s-]", "", title)[:80].strip().replace(" ", "_")

        frontmatter = {
            "created": ts.isoformat(),
            "type": "research-report",
            "confidence": f"{confidence:.2f}",
            "evidence_count": str(evidence_count),
            "tags": all_tags,
        }
        if quality_metrics:
            frontmatter["quality_score"] = str(quality_metrics.get("total_score", 0))

        # Build note body
        body_parts = [
            f"# {title}\n",
            f"*Дата: {ts.strftime('%Y-%m-%d %H:%M')} UTC*\n",
            f"*Уверенность: {confidence:.0%} | Доказательств: {evidence_count}*\n",
        ]

        # Quality metrics section
        if quality_metrics:
            body_parts.append("\n## Метрики качества\n")
            for k, v in quality_metrics.items():
                body_parts.append(f"- **{k}**: {v}")
            body_parts.append("")

        body_parts.append("\n## Отчёт\n")
        body_parts.append(report)

        if sources:
            body_parts.append("\n## Источники\n")
            for i, src in enumerate(sources, 1):
                body_parts.append(f"{i}. {src}")

        # Backlinks to related concepts
        body_parts.append("\n## Связи\n")
        body_parts.append("- [[Research/Reports]] | [[Knowledge/Concepts]]")

        # Tags
        body_parts.append(f"\n{'  '.join(f'#{t}' for t in all_tags)}")

        content = "\n".join(body_parts)
        rel_path = f"Research/Reports/{slug}.md"
        return self.save_note(rel_path, content, frontmatter=frontmatter, overwrite=True)

    def save_learning_log(
        self,
        task: str,
        outcome: str,  # "success", "partial", "failure"
        lessons: List[str],
        context: str = "",
        patterns_discovered: List[str] | None = None,
        improvements: List[str] | None = None,
    ) -> str:
        """Save a learning log entry for the cognitive evolution loop.

        Each log captures: what was attempted, what happened, what was learned.
        """
        ts = datetime.now(timezone.utc)
        date_str = ts.strftime("%Y-%m-%d")
        time_str = ts.strftime("%H:%M")

        frontmatter = {
            "created": ts.isoformat(),
            "type": "learning-log",
            "outcome": outcome,
            "task": task,
            "tags": ["learning", "auto-generated", f"outcome-{outcome}"],
        }

        body_parts = [
            f"# Learning Log: {task}\n",
            f"*{date_str} {time_str} UTC | Outcome: {outcome}*\n",
        ]

        if context:
            body_parts.append(f"\n## Контекст\n\n{context}\n")

        body_parts.append("\n## Извлечённые уроки\n")
        for lesson in lessons:
            body_parts.append(f"- {lesson}")

        if patterns_discovered:
            body_parts.append("\n## Обнаруженные паттерны\n")
            for pat in patterns_discovered:
                body_parts.append(f"- 🔄 {pat}")

        if improvements:
            body_parts.append("\n## Предложения по улучшению\n")
            for imp in improvements:
                body_parts.append(f"- 💡 {imp}")

        body_parts.append(f"\n## Связи\n\n- [[Learning/Logs]] | [[Pipeline/Sessions]]")
        body_parts.append(f"\n#learning #auto-generated #outcome-{outcome}")

        content = "\n".join(body_parts)
        slug = f"{date_str}_{re.sub(r'[^a-zA-Z0-9_]', '_', task)[:40]}"
        return self.save_note(
            f"Learning/Logs/{slug}.md",
            content,
            frontmatter=frontmatter,
        )

    def save_skill_note(
        self,
        skill_name: str,
        description: str,
        usage_pattern: str,
        success_rate: float = 0.0,
        examples: List[str] | None = None,
    ) -> str:
        """Save a discovered skill to the Obsidian vault skill library."""
        ts = datetime.now(timezone.utc)
        frontmatter = {
            "created": ts.isoformat(),
            "type": "skill",
            "success_rate": f"{success_rate:.2f}",
            "tags": ["skill", "auto-discovered"],
        }

        body_parts = [
            f"# Skill: {skill_name}\n",
            f"\n## Описание\n\n{description}\n",
            f"\n## Паттерн использования\n\n```\n{usage_pattern}\n```\n",
            f"\n*Успешность: {success_rate:.0%}*\n",
        ]

        if examples:
            body_parts.append("\n## Примеры\n")
            for ex in examples:
                body_parts.append(f"- {ex}")

        body_parts.append(f"\n## Связи\n\n- [[Learning/Skills]]")
        body_parts.append("\n#skill #auto-discovered")

        content = "\n".join(body_parts)
        slug = re.sub(r"[^\w-]", "_", skill_name.lower())[:60]
        return self.save_note(
            f"Learning/Skills/{slug}.md",
            content,
            frontmatter=frontmatter,
            overwrite=True,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        subfolder: str = "",
        max_results: int = 10,
    ) -> List[VaultNote]:
        """Full-text search across vault notes.

        Returns notes sorted by relevance (keyword match count).
        """
        notes = self.list_notes(subfolder)
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: List[tuple[float, VaultNote]] = []
        for note in notes:
            text = (note.title + " " + note.content).lower()
            # Score: exact phrase match + individual word matches
            score = 0.0
            if query_lower in text:
                score += 5.0
            for word in query_words:
                if len(word) > 2:
                    score += text.count(word) * 0.5
            if score > 0:
                scored.append((score, note))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [note for _, note in scored[:max_results]]

    def search_by_backlinks(self, target_note: str) -> List[VaultNote]:
        """Find all notes that link to a given note."""
        all_notes = self.list_notes()
        target_stem = Path(target_note).stem
        return [n for n in all_notes if target_stem in n.backlinks]

    # ------------------------------------------------------------------
    # Knowledge Graph
    # ------------------------------------------------------------------

    def build_knowledge_graph(self) -> Dict[str, KnowledgeGraphNode]:
        """Build the full knowledge graph from vault backlinks.

        Returns a dict mapping note paths to KnowledgeGraphNode objects,
        including bidirectional link tracking and degree centrality.
        """
        all_notes = self.list_notes()
        graph: Dict[str, KnowledgeGraphNode] = {}

        # First pass: create nodes
        for note in all_notes:
            graph[note.path] = KnowledgeGraphNode(
                note_path=note.path,
                title=note.title,
                links_to=[bl for bl in note.backlinks],
                tags=note.tags,
            )

        # Second pass: build reverse links (linked_from)
        stem_to_path: Dict[str, str] = {}
        for note in all_notes:
            stem = Path(note.path).stem
            stem_to_path[stem] = note.path

        for node in graph.values():
            for link_target in node.links_to:
                target_path = stem_to_path.get(link_target)
                if target_path and target_path in graph:
                    graph[target_path].linked_from.append(node.note_path)

        # Compute degree centrality
        for node in graph.values():
            node.degree = len(node.links_to) + len(node.linked_from)

        logger.info(
            "Knowledge graph built",
            nodes=len(graph),
            edges=sum(len(n.links_to) for n in graph.values()),
        )
        return graph

    def get_hub_notes(self, top_k: int = 10) -> List[KnowledgeGraphNode]:
        """Get the most connected notes (knowledge hubs)."""
        graph = self.build_knowledge_graph()
        nodes = sorted(graph.values(), key=lambda n: n.degree, reverse=True)
        return nodes[:top_k]

    # ------------------------------------------------------------------
    # Integration with Deep Research Pipeline
    # ------------------------------------------------------------------

    def persist_research_results(self, results: Dict[str, Any]) -> str:
        """Save DeepResearchPipeline output to Obsidian vault.

        Call this after pipeline.research() completes.
        """
        report = results.get("report", "")
        sources = results.get("sources", [])
        confidence = results.get("confidence_score", 0.0)
        evidence_count = results.get("evidence_count", 0)
        quality = results.get("quality_metrics", {})

        # Extract title from first line of report
        first_line = report.split("\n")[0] if report else "Research Report"
        title = re.sub(r"^[#\s*]+", "", first_line)[:100]

        return self.save_research_note(
            title=title,
            report=report,
            sources=sources,
            confidence=confidence,
            evidence_count=evidence_count,
            quality_metrics=quality,
        )

    def get_relevant_context(self, question: str, max_notes: int = 5) -> str:
        """Get relevant context from vault for a new research question.

        Call this before starting pipeline.research() to inject vault knowledge.
        """
        notes = self.search(question, max_results=max_notes)
        if not notes:
            return ""

        context_parts = []
        for note in notes:
            # Take first 500 chars of each relevant note
            snippet = note.content[:500]
            context_parts.append(
                f"### {note.title}\n{snippet}\n"
                f"Tags: {', '.join(note.tags[:5])}"
            )

        return "\n\n---\n\n".join(context_parts)
