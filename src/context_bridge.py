"""
Context Bridge — 3-layer persistent context transfer for cross-model swaps.

Solves the KV cache destruction problem when switching between
Qwen2.5-Coder-14B-AWQ ↔ DeepSeek-R1-distill-Qwen-14B-AWQ.

Architecture:
  Layer 1 — Summary Layer: structured JSON summaries generated before model unload
  Layer 2 — Fact Store: SQLite-backed persistent pipeline state
  Layer 3 — Embedding DB: ChromaDB semantic memory for long-term retrieval

Both models share the Qwen2 tokenizer, so text-level transfer is efficient.
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("ContextBridge")

# Default paths
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "context_bridge.db"


@dataclass
class PipelineSnapshot:
    """Serializable snapshot of pipeline state at swap point."""

    pipeline_id: str
    timestamp: float = field(default_factory=time.time)
    brigade: str = ""
    chain_position: int = 0
    source_model: str = ""
    target_model: str = ""
    accumulated_context: str = ""
    step_summaries: List[Dict[str, str]] = field(default_factory=list)
    pending_actions: List[str] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "PipelineSnapshot":
        return cls(**json.loads(raw))


# ---------------------------------------------------------------------------
# Layer 2 — Fact Store (SQLite)
# ---------------------------------------------------------------------------

class FactStore:
    """SQLite-backed persistent store for pipeline snapshots."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _DEFAULT_DB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_snapshots (
                pipeline_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                brigade TEXT NOT NULL,
                chain_position INTEGER NOT NULL,
                source_model TEXT NOT NULL,
                target_model TEXT NOT NULL,
                snapshot_json TEXT NOT NULL
            )
        """)
        # Keep max 50 snapshots (auto-cleanup old)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS context_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id TEXT NOT NULL,
                role TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (pipeline_id) REFERENCES pipeline_snapshots(pipeline_id)
            )
        """)
        self._conn.commit()

    def save_snapshot(self, snapshot: PipelineSnapshot) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO pipeline_snapshots
               (pipeline_id, timestamp, brigade, chain_position, source_model, target_model, snapshot_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.pipeline_id,
                snapshot.timestamp,
                snapshot.brigade,
                snapshot.chain_position,
                snapshot.source_model,
                snapshot.target_model,
                snapshot.to_json(),
            ),
        )
        self._conn.commit()
        self._cleanup_old()
        logger.info("Snapshot saved", pipeline_id=snapshot.pipeline_id)

    def load_snapshot(self, pipeline_id: str) -> Optional[PipelineSnapshot]:
        row = self._conn.execute(
            "SELECT snapshot_json FROM pipeline_snapshots WHERE pipeline_id = ?",
            (pipeline_id,),
        ).fetchone()
        if row:
            return PipelineSnapshot.from_json(row[0])
        return None

    def save_fact(self, pipeline_id: str, role: str, fact_type: str, content: str) -> None:
        self._conn.execute(
            """INSERT INTO context_facts (pipeline_id, role, fact_type, content, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (pipeline_id, role, fact_type, content, time.time()),
        )
        self._conn.commit()

    def get_facts(self, pipeline_id: str, limit: int = 20) -> List[Dict[str, str]]:
        rows = self._conn.execute(
            """SELECT role, fact_type, content FROM context_facts
               WHERE pipeline_id = ? ORDER BY timestamp DESC LIMIT ?""",
            (pipeline_id, limit),
        ).fetchall()
        return [{"role": r[0], "type": r[1], "content": r[2]} for r in rows]

    def _cleanup_old(self, keep: int = 50) -> None:
        count = self._conn.execute("SELECT COUNT(*) FROM pipeline_snapshots").fetchone()[0]
        if count > keep:
            excess = count - keep
            self._conn.execute(
                """DELETE FROM pipeline_snapshots WHERE pipeline_id IN
                    (SELECT pipeline_id FROM pipeline_snapshots
                     ORDER BY timestamp ASC LIMIT ?)""",
                (excess,),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Layer 3 — Embedding Store (ChromaDB semantic memory)
# ---------------------------------------------------------------------------

class EmbeddingStore:
    """ChromaDB-backed semantic memory for long-term context retrieval.

    Embeds pipeline snapshot summaries and enables semantic search
    across historical context transfers.

    Graceful degradation: if ChromaDB is unavailable, Layer 3 is disabled
    and Layer 1+2 continue to function normally.
    """

    def __init__(self, persist_dir: str = "data/context_embeddings", collection_name: str = "context_bridge"):
        self._enabled = False
        self._collection = None
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._init_chromadb()

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB with graceful degradation."""
        try:
            import chromadb
            Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._enabled = True
            logger.info("embedding_store_initialized", persist_dir=self._persist_dir)
        except ImportError:
            logger.info("chromadb_not_installed", msg="Layer 3 disabled — install chromadb for semantic search")
        except Exception as exc:
            logger.warning("embedding_store_init_failed", error=str(exc))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def store_embedding(self, snapshot: PipelineSnapshot) -> None:
        """Embed and store a pipeline snapshot summary."""
        if not self._enabled or not self._collection:
            return
        try:
            # Build text to embed from snapshot content
            text_parts = [
                f"Brigade: {snapshot.brigade}",
                f"Models: {snapshot.source_model} → {snapshot.target_model}",
            ]
            for step in snapshot.step_summaries:
                text_parts.append(f"{step.get('role', '')}: {step.get('summary', '')}")
            if snapshot.key_facts:
                text_parts.extend(snapshot.key_facts)
            document = "\n".join(text_parts)

            self._collection.upsert(
                ids=[snapshot.pipeline_id],
                documents=[document],
                metadatas=[{
                    "brigade": snapshot.brigade,
                    "source_model": snapshot.source_model,
                    "target_model": snapshot.target_model,
                    "timestamp": str(snapshot.timestamp),
                    "chain_position": str(snapshot.chain_position),
                }],
            )
            logger.debug("embedding_stored", pipeline_id=snapshot.pipeline_id)
        except Exception as exc:
            logger.warning("embedding_store_failed", error=str(exc), pipeline_id=snapshot.pipeline_id)

    def search_similar(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Semantic search across stored context embeddings."""
        if not self._enabled or not self._collection:
            return []
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, self._collection.count() or 1),
            )
            found = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                found.append({
                    "pipeline_id": doc_id,
                    "document": (results.get("documents", [[]])[0] or [""])[i] if results.get("documents") else "",
                    "metadata": (results.get("metadatas", [[]])[0] or [{}])[i] if results.get("metadatas") else {},
                    "distance": (results.get("distances", [[]])[0] or [0.0])[i] if results.get("distances") else 0.0,
                })
            return found
        except Exception as exc:
            logger.warning("embedding_search_failed", error=str(exc))
            return []

    def prune_old(self, max_age_hours: float = 24.0) -> int:
        """Remove embeddings older than max_age_hours."""
        if not self._enabled or not self._collection:
            return 0
        try:
            cutoff = time.time() - (max_age_hours * 3600)
            # Get all items and filter by timestamp
            all_items = self._collection.get()
            ids_to_delete = []
            for i, meta in enumerate(all_items.get("metadatas", [])):
                ts = float(meta.get("timestamp", "0"))
                if ts < cutoff and ts > 0:
                    ids_to_delete.append(all_items["ids"][i])
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                logger.info("embeddings_pruned", count=len(ids_to_delete), max_age_hours=max_age_hours)
            return len(ids_to_delete)
        except Exception as exc:
            logger.warning("embedding_prune_failed", error=str(exc))
            return 0

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the embedding store."""
        if not self._enabled:
            return {"enabled": False, "reason": "chromadb not available"}
        try:
            count = self._collection.count() if self._collection else 0
            return {"enabled": True, "count": count, "persist_dir": self._persist_dir}
        except Exception as exc:
            return {"enabled": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Main Context Bridge
# ---------------------------------------------------------------------------

class ContextBridge:
    """Orchestrates 3-layer context transfer between model swaps."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        bridge_cfg = (config or {}).get("context_bridge", {})
        db_path = bridge_cfg.get("fact_store_path", str(_DEFAULT_DB_PATH))
        self._enabled = bridge_cfg.get("enabled", True)
        self._summary_max_tokens = bridge_cfg.get("summary_max_tokens", 500)
        self._fact_store = FactStore(db_path)
        # Layer 3 — Embedding store
        embed_dir = bridge_cfg.get("embedding_dir", str(Path(_DEFAULT_DB_PATH).parent / "context_embeddings"))
        self._embedding_store = EmbeddingStore(persist_dir=embed_dir)
        logger.info(
            "ContextBridge initialized",
            enabled=self._enabled,
            db=db_path,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    # -- Layer 1: Summary generation --

    def build_handoff_summary(
        self,
        pipeline_id: str,
        brigade: str,
        chain_position: int,
        source_model: str,
        target_model: str,
        steps_results: List[Dict[str, str]],
        accumulated_context: str,
    ) -> PipelineSnapshot:
        """Build a structured snapshot before model swap."""
        step_summaries = []
        for step in steps_results:
            role = step.get("role", "unknown")
            resp = step.get("response", "")
            # Compress each step to key output (max 200 chars)
            summary = resp[:200].strip()
            if len(resp) > 200:
                boundary = max(summary.rfind(". "), summary.rfind("\n"))
                if boundary > 100:
                    summary = summary[:boundary + 1]
                summary += "..."
            step_summaries.append({"role": role, "summary": summary})

        snapshot = PipelineSnapshot(
            pipeline_id=pipeline_id,
            brigade=brigade,
            chain_position=chain_position,
            source_model=source_model,
            target_model=target_model,
            accumulated_context=accumulated_context[:self._summary_max_tokens * 4],
            step_summaries=step_summaries,
        )
        return snapshot

    # -- Layer 2: Persist --

    def save_before_swap(self, snapshot: PipelineSnapshot) -> None:
        """Persist snapshot to SQLite before model unload."""
        self._fact_store.save_snapshot(snapshot)
        # Also save individual step facts
        for step in snapshot.step_summaries:
            self._fact_store.save_fact(
                snapshot.pipeline_id,
                step["role"],
                "step_output",
                step["summary"],
            )

        # Layer 3: Embed for semantic search
        self._embedding_store.store_embedding(snapshot)

    def restore_after_swap(self, pipeline_id: str) -> Optional[str]:
        """Restore context as a formatted string after new model loads."""
        snapshot = self._fact_store.load_snapshot(pipeline_id)
        if not snapshot:
            logger.warning("No snapshot found for restore", pipeline_id=pipeline_id)
            return None

        facts = self._fact_store.get_facts(pipeline_id)

        # Layer 3: Semantic search for related context
        semantic_results = self._embedding_store.search_similar(
            f"{snapshot.brigade} {snapshot.source_model}", n_results=3
        )

        # Build context briefing for the new model
        lines = [
            f"[CONTEXT BRIDGE — transferred from {snapshot.source_model}]",
            f"Brigade: {snapshot.brigade}, Chain position: {snapshot.chain_position}",
            "",
            "Previous steps:",
        ]
        for step in snapshot.step_summaries:
            lines.append(f"  - {step['role']}: {step['summary']}")

        if snapshot.accumulated_context:
            lines.append("")
            lines.append("Accumulated context:")
            lines.append(snapshot.accumulated_context[:1000])

        if facts:
            lines.append("")
            lines.append("Key facts:")
            for f in facts[:10]:
                lines.append(f"  - [{f['role']}] {f['content'][:150]}")

        if semantic_results:
            lines.append("")
            lines.append("Related context (semantic):")
            for sr in semantic_results[:3]:
                if sr["pipeline_id"] != pipeline_id:  # Skip self
                    doc_preview = sr.get("document", "")[:200]
                    lines.append(f"  - [{sr['pipeline_id'][:12]}] {doc_preview}")

        return "\n".join(lines)

    def close(self) -> None:
        self._fact_store.close()

    def health_check(self) -> Dict[str, Any]:
        """Return health status of all layers."""
        return {
            "enabled": self._enabled,
            "layer2_fact_store": "ok",
            "layer3_embeddings": self._embedding_store.health_check(),
        }
