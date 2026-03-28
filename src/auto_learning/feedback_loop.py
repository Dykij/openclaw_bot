"""Auto-Learning Feedback Loop — Self-Improvement via pattern extraction.

After each successful pipeline commit to Dmarket_bot, this module:
1. Extracts the "successful code pattern" from the diff
2. Scores it by complexity and reusability
3. Stores it in src/ai/agents/special_skills.json

The stored patterns are used as few-shot examples in future pipeline runs,
enabling continuous learning from past successes.

Reference: Complementary RL (arXiv:2603.17621), SLEA-RL step-level
experience augmentation (arXiv:2603.18079) — collected in data/research/v11.6.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("FeedbackLoop")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CodePattern:
    """An extracted successful code pattern."""
    pattern_id: str
    description: str
    language: str
    code_snippet: str
    source_file: str
    commit_hash: str = ""
    score: float = 0.0
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    use_count: int = 0


@dataclass
class FeedbackEntry:
    """A single feedback loop entry."""
    commit_hash: str
    patterns_extracted: int
    patterns_stored: int
    elapsed_sec: float
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Pattern extraction heuristics
# ---------------------------------------------------------------------------

_PATTERN_MARKERS = [
    # Functions with docstrings (Python)
    re.compile(r'^\+\s*(?:async\s+)?def\s+(\w+)\(.*?\).*?:\s*$', re.MULTILINE),
    # Functions (TypeScript/Rust)
    re.compile(r'^\+\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', re.MULTILINE),
    re.compile(r'^\+\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', re.MULTILINE),
    # Class definitions
    re.compile(r'^\+\s*class\s+(\w+)', re.MULTILINE),
    # Struct/Impl (Rust)
    re.compile(r'^\+\s*(?:pub\s+)?(?:struct|impl)\s+(\w+)', re.MULTILINE),
]

_ERROR_HANDLING_PATTERN = re.compile(r'(?:try|except|catch|Result<|anyhow|\.unwrap_or)', re.IGNORECASE)
_ASYNC_PATTERN = re.compile(r'\basync\b|\bawait\b')
_COMMENT_RATIO_MIN = 0.05  # minimum comment-to-code ratio for high score


def _extract_added_code(diff: str) -> List[str]:
    """Extract added code blocks from a unified diff."""
    blocks: List[str] = []
    current_block: List[str] = []

    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            current_block.append(line[1:])  # strip the +
        else:
            if current_block:
                code = "\n".join(current_block).strip()
                if len(code) > 20:  # ignore trivial additions
                    blocks.append(code)
                current_block = []

    if current_block:
        code = "\n".join(current_block).strip()
        if len(code) > 20:
            blocks.append(code)

    return blocks


def _score_pattern(code: str) -> float:
    """Score a code pattern 0.0-1.0 based on quality heuristics."""
    score = 0.5  # base

    # Bonus for error handling
    if _ERROR_HANDLING_PATTERN.search(code):
        score += 0.1

    # Bonus for async patterns
    if _ASYNC_PATTERN.search(code):
        score += 0.05

    # Bonus for type hints (Python)
    type_hint_count = len(re.findall(r':\s*(?:str|int|float|bool|list|dict|Optional|List|Dict)', code))
    score += min(type_hint_count * 0.02, 0.1)

    # Bonus for docstrings/comments
    total_lines = len(code.splitlines())
    comment_lines = len(re.findall(r'^\s*(?:#|//|/\*|\*|""")', code, re.MULTILINE))
    if total_lines > 0 and (comment_lines / total_lines) >= _COMMENT_RATIO_MIN:
        score += 0.1

    # Bonus for reasonable length (not too short, not too long)
    if 5 <= total_lines <= 50:
        score += 0.1
    elif total_lines > 50:
        score -= 0.05

    return max(0.0, min(1.0, round(score, 2)))


def _detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    lang_map = {".py": "python", ".ts": "typescript", ".rs": "rust", ".js": "javascript"}
    return lang_map.get(ext, "unknown")


def _extract_tags(code: str) -> List[str]:
    """Extract semantic tags from a code pattern."""
    tags: List[str] = []
    if _ASYNC_PATTERN.search(code):
        tags.append("async")
    if _ERROR_HANDLING_PATTERN.search(code):
        tags.append("error-handling")
    if re.search(r'\btest\b|\bassert\b', code, re.IGNORECASE):
        tags.append("testing")
    if re.search(r'\bapi\b|\bhttp\b|\bfetch\b|\brequest\b', code, re.IGNORECASE):
        tags.append("api")
    if re.search(r'\bparse\b|\bjson\b|\bserde\b', code, re.IGNORECASE):
        tags.append("parsing")
    if re.search(r'\bcache\b|\bmemo\b', code, re.IGNORECASE):
        tags.append("caching")
    return tags


# ---------------------------------------------------------------------------
# Feedback Loop Engine
# ---------------------------------------------------------------------------

_DEFAULT_SKILLS_PATH = "src/ai/agents/special_skills.json"
_MAX_PATTERNS = 200  # maximum stored patterns before pruning


class FeedbackLoopEngine:
    """Self-improvement engine that learns from successful commits.

    Usage:
        engine = FeedbackLoopEngine(project_root="/path/to/project")
        entry = await engine.process_commit("abc123")
    """

    def __init__(
        self,
        project_root: str,
        skills_path: Optional[str] = None,
    ):
        self.project_root = os.path.abspath(project_root)
        self.skills_path = os.path.join(
            self.project_root,
            skills_path or _DEFAULT_SKILLS_PATH,
        )
        self._patterns: List[CodePattern] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing patterns from disk."""
        if os.path.exists(self.skills_path):
            try:
                with open(self.skills_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._patterns = [
                    CodePattern(**p) for p in data.get("patterns", [])
                ]
                logger.info("feedback_loop_loaded", count=len(self._patterns))
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("feedback_loop_load_error", error=str(e))
                self._patterns = []

    def _save(self) -> None:
        """Persist patterns to disk."""
        os.makedirs(os.path.dirname(self.skills_path), exist_ok=True)
        data = {
            "version": "11.7",
            "updated_at": time.time(),
            "total_patterns": len(self._patterns),
            "patterns": [asdict(p) for p in self._patterns],
        }
        with open(self.skills_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("feedback_loop_saved", count=len(self._patterns))

    async def process_commit(self, commit_hash: str = "HEAD") -> FeedbackEntry:
        """Extract patterns from a commit diff and store the best ones."""
        start = time.monotonic()

        diff = self._get_commit_diff(commit_hash)
        if not diff:
            return FeedbackEntry(
                commit_hash=commit_hash,
                patterns_extracted=0,
                patterns_stored=0,
                elapsed_sec=round(time.monotonic() - start, 2),
            )

        # Extract code blocks from the diff
        added_blocks = _extract_added_code(diff)
        patterns: List[CodePattern] = []

        # Get the list of changed files for language detection
        changed_files = self._get_changed_files(commit_hash)

        for block in added_blocks:
            score = _score_pattern(block)
            if score < 0.5:
                continue  # skip low-quality patterns

            # Determine source file (best guess: first matching file)
            source_file = ""
            for cf in changed_files:
                if any(name in block for name in [Path(cf).stem]):
                    source_file = cf
                    break
            if not source_file and changed_files:
                source_file = changed_files[0]

            lang = _detect_language(source_file) if source_file else "unknown"

            pattern_id = sha256(block.encode()).hexdigest()[:12]

            # Skip duplicates
            if any(p.pattern_id == pattern_id for p in self._patterns):
                continue

            # Generate description from first line or function name
            first_line = block.splitlines()[0].strip()
            desc = first_line[:100] if first_line else "Extracted pattern"

            patterns.append(CodePattern(
                pattern_id=pattern_id,
                description=desc,
                language=lang,
                code_snippet=block[:500],  # cap at 500 chars
                source_file=source_file,
                commit_hash=commit_hash,
                score=score,
                tags=_extract_tags(block),
            ))

        # Store the best patterns
        stored = 0
        for p in sorted(patterns, key=lambda x: x.score, reverse=True)[:5]:
            self._patterns.append(p)
            stored += 1

        # Prune if over limit
        if len(self._patterns) > _MAX_PATTERNS:
            self._patterns.sort(key=lambda x: x.score, reverse=True)
            self._patterns = self._patterns[:_MAX_PATTERNS]

        if stored > 0:
            self._save()

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            "feedback_loop_processed",
            commit=commit_hash[:8],
            extracted=len(patterns),
            stored=stored,
            elapsed_sec=elapsed,
        )

        return FeedbackEntry(
            commit_hash=commit_hash,
            patterns_extracted=len(patterns),
            patterns_stored=stored,
            elapsed_sec=elapsed,
        )

    def get_relevant_patterns(
        self,
        query: str,
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[CodePattern]:
        """Retrieve the most relevant stored patterns for a task."""
        candidates = self._patterns
        if language:
            candidates = [p for p in candidates if p.language == language]

        # Simple keyword relevance scoring
        query_words = set(query.lower().split())
        scored: List[tuple[float, CodePattern]] = []
        for p in candidates:
            relevance = 0.0
            p_words = set(
                p.description.lower().split()
                + p.tags
                + p.code_snippet.lower().split()[:20]
            )
            overlap = query_words & p_words
            relevance = len(overlap) / max(len(query_words), 1)
            relevance += p.score * 0.3  # quality bonus
            scored.append((relevance, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [p for _, p in scored[:top_k]]

        # Mark as used
        for p in results:
            p.use_count += 1

        return results

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _get_commit_diff(self, commit_hash: str) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", f"{commit_hash}^", commit_hash, "--", "*.py", "*.ts", "*.rs"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _get_changed_files(self, commit_hash: str) -> List[str]:
        try:
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []
