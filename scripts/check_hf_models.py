import os
os.environ["HF_HOME"] = "/mnt/d/vllm_models"
from huggingface_hub import HfApi

api = HfApi()
token = api.token
print("HF token set:", bool(token))

repos = [
    "solidrust/DeepSeek-R1-Distill-Qwen-14B-AWQ",
    "hugging-quants/DeepSeek-R1-Distill-Qwen-14B-AWQ-INT4",
    "casperhansen/deepseek-r1-distill-qwen-14b-awq",
    "Qwen/Qwen2.5-14B-Instruct-AWQ",
    "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
]
for repo in repos:
    try:
        info = api.model_info(repo)
        print("OK:", repo, "private:", info.private)
    except Exception as e:
        print("FAIL:", repo, "->", type(e).__name__, str(e)[:100])
