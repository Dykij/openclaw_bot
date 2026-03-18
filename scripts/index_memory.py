import asyncio
import json
import os
from typing import List

import aiohttp

MEMORY_BANK_DIR = ".memory-bank"
INDEX_FILE = os.path.join(MEMORY_BANK_DIR, "embeddings.json")

def get_config_url():
    config_path = "config/openclaw_config.json"
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
                url = cfg.get("system", {}).get("ollama_url", "http://localhost:11434")
                if "host.docker.internal" in url:
                    return url.replace("host.docker.internal", "127.0.0.1")
                return url
    except:
        pass
    return "http://localhost:11434"

OLLAMA_URL = get_config_url()
EMBED_MODEL = "nomic-embed-text:latest"

async def get_embeddings(text: str) -> List[float]:
    async with aiohttp.ClientSession(trust_env=False) as session:
        try:
            async with session.post(f"{OLLAMA_URL}/api/embeddings", json={
                "model": EMBED_MODEL,
                "prompt": text
            }, timeout=10, proxy=None) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("embedding", [])
        except Exception as e:
            print(f"Error embedding: {e}")
    return []

async def index_files():
    if not os.path.exists(INDEX_FILE):
        index = {}
    else:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)

    files = {
        "hot": os.path.join(MEMORY_BANK_DIR, "Hot_Memory.md"),
        "domain": os.path.join(MEMORY_BANK_DIR, "Domain_Experts.md"),
        "cold": os.path.join(MEMORY_BANK_DIR, "Cold_Memory.md")
    }

    processed_count = 0
    for tier, path in files.items():
        if not os.path.exists(path):
            continue
        
        print(f"Indexing {path} ({tier})...")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Simple chunking: split by sections (headers)
        chunks = content.split("###")
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if not chunk: continue
            
            snippet_id = f"{tier}_{i}"
            if snippet_id in index:
                continue
            
            print(f"  Embedding snippet {i}...")
            vector = await get_embeddings(chunk)
            if vector:
                index[snippet_id] = {
                    "text": f"### {chunk}" if i > 0 else chunk,
                    "tier": tier,
                    "vector": vector
                }
                processed_count += 1

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    
    print(f"Indexing complete. Processed {processed_count} new snippets.")

if __name__ == "__main__":
    asyncio.run(index_files())
