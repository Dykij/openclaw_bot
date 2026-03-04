import asyncio
import os
from typing import Dict, List, Optional

import aiohttp

class MemoryGarbageCollector:
    """
    Brigade: OpenClaw
    Role: Memory GC
    Model: llama3.2 (previously llama3.1:8b)
    
    Responsible for summarizing long conversation histories to prevent
    context window overflow, ensuring the 8GB VRAM limit on the RX 6600
    is respected by keeping input tokens small.
    """
    def __init__(self, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = "llama3.2"
        
    async def summarize_history(self, history: List[Dict[str, str]]) -> str:
        """
        Sends the dialogue history to Phi-4 and requests a compressed TL;DR summary.
        Appends keep_alive=0 to immediately free VRAM for the next agent.
        """
        # Convert history to a single string block
        raw_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        
        prompt = (
            "You are the Memory Garbage Collector for the OpenClaw system. "
            "Summarize the following interaction history into a strict, highly compressed "
            "'Context Briefing'. Retain only the most crucial technical facts, latest states, "
            "and active tasks. Omit metadata and pleasantries.\n\n"
            f"HISTORY:\n{raw_text}"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30s", # Smart flush instead of immediate 0 to allow batching
            "options": {
                "num_ctx": 2048
            }
        }

        async def _run_inference():
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(f"{self.ollama_url}/api/generate", json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("response", "").strip()
                        else:
                            print(f"GC API Error: {response.status}")
                            return "ERROR_SUMMARIZING_CONTEXT"
                except Exception as e:
                    print(f"GC Exception: {e}")
                    return "ERROR_SUMMARIZING_CONTEXT"
                    
        from task_queue import model_queue
        return await model_queue.enqueue(self.model, _run_inference)

    def truncate_and_replace(self, history: List[Dict[str, str]], summary: str) -> List[Dict[str, str]]:
        """
        Replaces the old history with the new summary.
        Keeps the system prompt intact if it exists.
        """
        new_history = []
        if history and history[0].get("role") == "system":
            new_history.append(history[0])
            
        new_history.append({"role": "system", "content": f"[CONTEXT BRIEFING]\n{summary}"})
        return new_history

# ======= Example Usage =======
async def run_demo():
    gc = MemoryGarbageCollector()
    mock_history = [
        {"role": "user", "content": "Update the API endpoint to v2 and add error handling."},
        {"role": "assistant", "content": "I have updated the API endpoint to v2 and added try-except blocks. Here is the code..."},
        {"role": "user", "content": "Now add a retry mechanism using tenacity."}
    ]
    
    print("Running GC Summarization...")
    # NOTE: Will fail if Ollama is not running locally.
    # summary = await gc.summarize_history(mock_history)
    # print(f"Summary: {summary}")
