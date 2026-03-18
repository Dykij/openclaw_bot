import json
import sys
try:
    with open("config/openclaw_config.json", "r", encoding="utf-8") as f:
        json.load(f)
    print("JSON OK")
except json.JSONDecodeError as e:
    print(f"JSON ERROR: {e}")
    sys.exit(1)
