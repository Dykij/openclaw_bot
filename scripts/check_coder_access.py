#!/usr/bin/env python3
"""Check nvidia/Qwen2.5-Coder-14B-Instruct-NVFP4 access and find alternatives."""
import os
os.environ["HF_HOME"] = "/mnt/d/vllm_models"

from huggingface_hub import HfApi
api = HfApi()

print("=== Checking nvidia/Qwen2.5-Coder-14B-Instruct-NVFP4 ===")
try:
    info = api.model_info("nvidia/Qwen2.5-Coder-14B-Instruct-NVFP4")
    gated = getattr(info, 'gated', 'unknown')
    print(f"Model accessible! gated={gated}")
    st_size = sum(s.size for s in info.siblings if s.size and s.rfilename.endswith('.safetensors'))
    print(f"Size: {st_size/1024**3:.2f} GB")
except Exception as e:
    print(f"Cannot access: {str(e)[:200]}")

print("\n=== Searching for ungated Qwen2.5-Coder NVFP4 alternatives ===")
results = list(api.list_models(search="Qwen2.5-Coder NVFP4", limit=20))
for m in results:
    print(f"  {m.id} (downloads={m.downloads})")

print("\n=== Searching for Qwen2.5-Coder-14B alternatives (any quant) ===")
results2 = list(api.list_models(search="Qwen2.5-Coder-14B", sort="downloads", direction=-1, limit=30))
for m in results2:
    mid = m.id.lower()
    if "nvfp4" in mid or "fp4" in mid or "awq" in mid or "gptq" in mid:
        print(f"  {m.id} (downloads={m.downloads})")

print("\n=== Check HF token ===")
token_path1 = os.path.expanduser("~/.cache/huggingface/token")
token_path2 = "/mnt/d/vllm_models/token"
for p in [token_path1, token_path2]:
    if os.path.exists(p):
        print(f"Token found at {p}")
    else:
        print(f"No token at {p}")

# Check if huggingface-cli login was done
import subprocess
result = subprocess.run(["/mnt/d/vllm_env/bin/python3", "-c", 
    "from huggingface_hub import HfFolder; print('Token:', bool(HfFolder.get_token()))"], 
    capture_output=True, text=True)
print(f"HfFolder token: {result.stdout.strip()}")
