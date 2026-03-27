"""
OpenClaw vLLM Benchmark — measures response time and token generation speed.
Usage: python scripts/benchmark_vllm.py [--url http://localhost:8000/v1]
"""

import argparse
import json
import time
import urllib.request
import urllib.error


def benchmark_request(url: str, model: str, prompt: str, max_tokens: int = 256) -> dict:
    """Send a single chat completion request and measure timing."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
        "temperature": 0.1,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": str(e), "elapsed_s": time.perf_counter() - start}

    elapsed = time.perf_counter() - start

    usage = body.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    content = body["choices"][0]["message"]["content"] if body.get("choices") else ""

    tok_per_sec = completion_tokens / elapsed if elapsed > 0 else 0

    return {
        "elapsed_s": round(elapsed, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tok_per_sec": round(tok_per_sec, 2),
        "response_preview": content[:200],
    }


def get_loaded_model(url: str) -> str | None:
    """Get the currently loaded model name from vLLM."""
    try:
        req = urllib.request.Request(f"{url}/models")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            if models:
                return models[0]["id"]
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="OpenClaw vLLM Benchmark")
    parser.add_argument("--url", default="http://localhost:8000/v1", help="vLLM base URL")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    print(f"=== OpenClaw vLLM Benchmark ===")
    print(f"URL: {url}")

    model = get_loaded_model(url)
    if not model:
        print("ERROR: vLLM server not reachable or no model loaded.")
        return
    print(f"Model: {model}\n")

    tests = [
        ("Ping (1 tok)", "Привет", 8),
        ("Short answer", "Что такое REST API? Кратко.", 64),
        ("Code generation", "Напиши Python функцию для сортировки списка словарей по ключу 'price' по убыванию.", 256),
        ("Complex analysis", "Объясни разницу между async/await и threading в Python. Когда использовать что? Приведи примеры.", 512),
    ]

    results = []
    for name, prompt, max_tok in tests:
        print(f"[{name}] max_tokens={max_tok}...")
        r = benchmark_request(url, model, prompt, max_tok)
        if "error" in r:
            print(f"  ERROR: {r['error']}")
        else:
            print(f"  Time: {r['elapsed_s']}s | Tokens: {r['completion_tokens']} | Speed: {r['tok_per_sec']} tok/s")
            print(f"  Preview: {r['response_preview'][:100]}...")
        results.append({"test": name, **r})
        print()

    # Summary
    valid = [r for r in results if "error" not in r and r.get("tok_per_sec", 0) > 0]
    if valid:
        avg_speed = sum(r["tok_per_sec"] for r in valid) / len(valid)
        avg_time = sum(r["elapsed_s"] for r in valid) / len(valid)
        print("=== SUMMARY ===")
        print(f"Average speed: {avg_speed:.1f} tok/s")
        print(f"Average time:  {avg_time:.1f}s")
        print(f"Tests passed:  {len(valid)}/{len(results)}")


if __name__ == "__main__":
    main()
