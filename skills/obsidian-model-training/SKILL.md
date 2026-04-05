---
name: obsidian-model-training
description: "Extract knowledge from Obsidian vaults for LLM training and fine-tuning: vault parsing, JSONL dataset generation, QA pair extraction, knowledge graph building. Use when: converting Obsidian notes to training data, building datasets from vault knowledge, feeding vault content into RAG/SuperMemory."
version: 1.0.0
---

# Obsidian Model Training

## Purpose

Transform Obsidian vault content into structured training data for LLM fine-tuning, RAG ingestion, and knowledge base construction.

## Pipeline Overview

```
Obsidian Vault
    ├── Parse markdown files
    ├── Extract frontmatter metadata
    ├── Resolve [[wikilinks]] → full content
    ├── Build knowledge graph from links
    └── Generate training datasets
          ├── QA pairs (JSONL)
          ├── Instruction-response (Alpaca format)
          ├── Embeddings (for ChromaDB/SuperMemory)
          └── Conversation turns (ShareGPT format)
```

## Vault Parser

```python
import re
from pathlib import Path
from dataclasses import dataclass, field
import yaml

@dataclass
class Note:
    path: Path
    title: str
    content: str
    frontmatter: dict = field(default_factory=dict)
    outlinks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

def parse_vault(vault_path: str) -> list[Note]:
    """Parse all markdown files in an Obsidian vault."""
    notes = []
    vault = Path(vault_path)
    for md_file in vault.rglob("*.md"):
        if ".obsidian" in md_file.parts or "node_modules" in md_file.parts:
            continue
        text = md_file.read_text(encoding="utf-8")
        frontmatter = {}
        content = text
        # Parse YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                content = parts[2].strip()
        # Extract wikilinks
        outlinks = re.findall(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]', content)
        # Extract tags
        tags = re.findall(r'#([a-zA-Z][\w/]+)', content)
        if isinstance(frontmatter.get("tags"), list):
            tags.extend(frontmatter["tags"])
        notes.append(Note(
            path=md_file.relative_to(vault),
            title=md_file.stem,
            content=content,
            frontmatter=frontmatter,
            outlinks=outlinks,
            tags=list(set(tags)),
        ))
    return notes
```

## Dataset Generation

### QA Pairs (JSONL)

```python
import json

def vault_to_qa_jsonl(notes: list[Note], output_path: str):
    """Convert vault notes to question-answer training pairs."""
    with open(output_path, "w", encoding="utf-8") as f:
        for note in notes:
            if len(note.content.strip()) < 50:
                continue
            # Generate QA pair
            entry = {
                "instruction": f"Расскажи о: {note.title}",
                "input": "",
                "output": note.content[:4000],
                "source": str(note.path),
                "tags": note.tags,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # Generate concept explanation pair
            if note.tags:
                entry2 = {
                    "instruction": f"Объясни концепцию {note.title} в контексте {', '.join(note.tags[:3])}",
                    "input": "",
                    "output": note.content[:4000],
                    "source": str(note.path),
                }
                f.write(json.dumps(entry2, ensure_ascii=False) + "\n")
```

### ShareGPT Format (multi-turn conversations)

```python
def vault_to_sharegpt(notes: list[Note], output_path: str):
    """Convert notes to ShareGPT conversation format."""
    conversations = []
    for note in notes:
        if len(note.content) < 100:
            continue
        conv = {
            "conversations": [
                {"from": "human", "value": f"Что ты знаешь о {note.title}?"},
                {"from": "gpt", "value": note.content[:4000]},
            ],
            "source": str(note.path),
        }
        conversations.append(conv)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)
```

### Embeddings for SuperMemory / ChromaDB

```python
import chromadb

def vault_to_chromadb(notes: list[Note], db_path: str = "./chroma_vault"):
    """Ingest vault notes into ChromaDB for RAG."""
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name="obsidian_knowledge",
        metadata={"hnsw:space": "cosine"},
    )
    # Chunk large notes into ~500 token segments
    for note in notes:
        chunks = _chunk_text(note.content, max_tokens=500)
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=[f"{note.path}__chunk_{i}"],
                metadatas=[{
                    "title": note.title,
                    "path": str(note.path),
                    "tags": ",".join(note.tags),
                    "chunk_index": i,
                }],
            )

def _chunk_text(text: str, max_tokens: int = 500) -> list[str]:
    """Split text into chunks, respecting paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) > max_tokens * 4:  # ~4 chars per token
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_tokens * 4]]
```

## Knowledge Graph from Wikilinks

```python
def build_knowledge_graph(notes: list[Note]) -> dict[str, list[str]]:
    """Build adjacency list from [[wikilinks]]."""
    title_map = {n.title.lower(): n.title for n in notes}
    graph = {n.title: [] for n in notes}
    for note in notes:
        for link in note.outlinks:
            target = title_map.get(link.lower())
            if target and target != note.title:
                graph[note.title].append(target)
    return graph
```

## CLI Usage

```bash
# Parse vault and generate training data
python -c "
from skills.obsidian_model_training import parse_vault, vault_to_qa_jsonl
notes = parse_vault('D:/ObsidianVault')
vault_to_qa_jsonl(notes, 'data/training/vault_qa.jsonl')
print(f'Generated {len(notes)} training pairs')
"

# Ingest into ChromaDB for RAG
python -c "
from skills.obsidian_model_training import parse_vault, vault_to_chromadb
notes = parse_vault('D:/ObsidianVault')
vault_to_chromadb(notes)
print(f'Ingested {len(notes)} notes into ChromaDB')
"
```

## Integration with OpenClaw Pipeline

1. **SuperMemory**: Ingest vault → ChromaDB → RAG retrieval in pipeline
2. **Training**: Vault → JSONL → fine-tune via OpenRouter (if supported) or HuggingFace
3. **Knowledge refresh**: Schedule periodic vault re-parse + embedding update
4. **Quality filter**: Skip notes <50 chars, drafts (tag: #draft), templates

## Rules

1. NEVER include personal/sensitive data in training sets
2. ALWAYS filter out `.obsidian/` config directory
3. Respect note tags: skip `#private`, `#draft`, `#template`
4. Chunk large notes — don't exceed model context limits
5. Deduplicate content that appears in multiple notes via wikilinks
