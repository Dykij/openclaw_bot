"""Benchmark vLLM token generation speed."""
import urllib.request
import json
import time

URL = "http://localhost:8000/v1/completions"
MODEL = "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"

PROMPTS = [
    "Write a Python function that implements binary search in a sorted array.",
    "Explain the difference between TCP and UDP in simple terms.",
    "Create a Rust struct for a linked list with insert and delete methods.",
    "What are the SOLID principles in software engineering? Give examples.",
    "Write a JavaScript async function that fetches data from an API with retry logic.",
]

def run_benchmark():
    results = []
    for i, prompt in enumerate(PROMPTS):
        data = json.dumps({
            "model": MODEL,
            "prompt": prompt,
            "max_tokens": 512,
            "temperature": 0.7,
        }).encode()
        req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
        start = time.time()
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        elapsed = time.time() - start
        tokens = result["usage"]["completion_tokens"]
        tps = tokens / elapsed if elapsed > 0 else 0
        results.append({"prompt_i": i + 1, "tokens": tokens, "time": elapsed, "tps": tps})
        print(f"[{i+1}/5] {tokens} tokens in {elapsed:.2f}s = {tps:.1f} tok/s")

    avg_tps = sum(r["tps"] for r in results) / len(results)
    max_tps = max(r["tps"] for r in results)
    min_tps = min(r["tps"] for r in results)
    total_tokens = sum(r["tokens"] for r in results)
    total_time = sum(r["time"] for r in results)
    print(f"\n=== BENCHMARK RESULTS (speculative + enforce-eager) ===")
    print(f"Total: {total_tokens} tokens in {total_time:.2f}s")
    print(f"Avg: {avg_tps:.1f} tok/s")
    print(f"Min: {min_tps:.1f} tok/s")
    print(f"Max: {max_tps:.1f} tok/s")
    print(f"Overall throughput: {total_tokens/total_time:.1f} tok/s")

if __name__ == "__main__":
    run_benchmark()
