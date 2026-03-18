#!/usr/bin/env python3
"""
Entry-point for documentation ingestion into .memory-bank/docs/

Runs the doc_ingester pipeline for all configured documentation sources
so that models in OpenClaw can reference them via RAG search.

Usage:
    python scripts/ingest_docs.py              # Ingest all default sources
    python scripts/ingest_docs.py --url URL    # Ingest a single URL
    python scripts/ingest_docs.py --index      # Rebuild vector index after ingestion
"""
import argparse
import os
import subprocess
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.doc_ingester import DEFAULT_SOURCES, ingest_all, ingest_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documentation into .memory-bank/docs/")
    parser.add_argument("--url", help="Ingest a single URL instead of all defaults")
    parser.add_argument(
        "--index",
        action="store_true",
        help="After ingestion, rebuild the vector index via scripts/index_memory.py",
    )
    args = parser.parse_args()

    if args.url:
        print(f"[ingest_docs] Ingesting single URL: {args.url}")
        ingest_url(args.url)
        print("[ingest_docs] Done.")
    else:
        print(f"[ingest_docs] Ingesting {len(DEFAULT_SOURCES)} documentation sources...")
        for i, url in enumerate(DEFAULT_SOURCES, 1):
            print(f"  [{i}/{len(DEFAULT_SOURCES)}] {url}")
        ingest_all(DEFAULT_SOURCES)
        print("[ingest_docs] All sources ingested.")

    if args.index:
        print("[ingest_docs] Rebuilding vector index...")
        index_script = os.path.join(os.path.dirname(__file__), "index_memory.py")
        if os.path.exists(index_script):
            subprocess.run([sys.executable, index_script], check=False)
        else:
            print("[ingest_docs] WARNING: scripts/index_memory.py not found, skipping index rebuild.")

    print("[ingest_docs] Complete. Docs saved to .memory-bank/docs/")


if __name__ == "__main__":
    main()
