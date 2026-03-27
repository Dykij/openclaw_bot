#!/usr/bin/env python3
import json, sys
path = '/mnt/d/openclaw_bot/openclaw_bot/data/training/raw_dialogues.jsonl'
ok = 0
for i, line in enumerate(open(path, encoding='utf-8'), 1):
    try:
        obj = json.loads(line)
        assert 'instruction' in obj and 'response' in obj, f"Строка {i}: отсутствует instruction или response"
        ok += 1
    except Exception as e:
        print(f"ОШИБКА строка {i}: {e}")
        sys.exit(1)
print(f"Все {ok} строк валидны")
