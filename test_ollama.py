import requests
import sys

url = "http://172.27.192.1:11434/api/tags"
print(f"Testing connection to {url}")
try:
    resp = requests.get(url, timeout=5)
    print(f"Success! Status: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
