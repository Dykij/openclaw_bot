import requests, time

url = 'http://localhost:8000/v1/chat/completions'
results = []
prompts = [
    'Объясни разницу между TCP и UDP в 3 предложениях.',
    'Напиши функцию Python для бинарного поиска.',
    'Что такое VRAM и зачем она нужна для LLM?',
]
for p in prompts:
    payload = {
        'model': 'Qwen/Qwen2.5-Coder-14B-Instruct-AWQ',
        'messages': [{'role': 'user', 'content': p}],
        'stream': False,
        'max_tokens': 512,
        'temperature': 0.7
    }
    try:
        start = time.time()
        r = requests.post(url, json=payload, timeout=120)
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json()
            usage = data.get('usage', {})
            ct = usage.get('completion_tokens', 0)
            tps = ct / elapsed if elapsed > 0 else 0
            results.append((p[:40], ct, elapsed, tps))
            print(f'[OK] {p[:40]}... | {ct} tok | {elapsed:.2f}s | {tps:.1f} tok/s')
        else:
            print(f'[ERR] {p[:40]}... | HTTP {r.status_code}')
    except Exception as e:
        print(f'[FAIL] {p[:40]}... | {e}')

if results:
    avg_tps = sum(r[3] for r in results) / len(results)
    total_tok = sum(r[1] for r in results)
    total_time = sum(r[2] for r in results)
    print()
    print('=== BENCHMARK SUMMARY ===')
    print(f'Total tokens: {total_tok}')
    print(f'Total time: {total_time:.2f}s')
    print(f'Average speed: {avg_tps:.1f} tok/s')
    print(f'Overall throughput: {total_tok/total_time:.1f} tok/s')
