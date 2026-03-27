import requests, time, json

url = 'http://localhost:8000/v1/chat/completions'
payload = {
    'model': 'Qwen/Qwen2.5-Coder-14B-Instruct-AWQ',
    'messages': [{'role': 'user', 'content': 'Напиши 5 фактов о Python. Будь кратким.'}],
    'stream': False,
    'max_tokens': 256,
    'temperature': 0.7
}
try:
    start = time.time()
    r = requests.post(url, json=payload, timeout=60)
    elapsed = time.time() - start
    if r.status_code == 200:
        data = r.json()
        usage = data.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total = usage.get('total_tokens', 0)
        tok_per_sec = completion_tokens / elapsed if elapsed > 0 else 0
        print('Status: OK')
        print('Model:', data['model'])
        print('Prompt tokens:', prompt_tokens)
        print('Completion tokens:', completion_tokens)
        print('Total tokens:', total)
        print(f'Time: {elapsed:.2f}s')
        print(f'Speed: {tok_per_sec:.1f} tok/s')
        print('Response:', data['choices'][0]['message']['content'][:200])
    else:
        print(f'Error: HTTP {r.status_code}')
        print(r.text[:300])
except Exception as e:
    print(f'Connection failed: {e}')
