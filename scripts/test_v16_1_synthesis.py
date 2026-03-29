import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipeline_executor import PipelineExecutor
from src.pipeline._logic_provider import OBSIDIAN_DIR
import structlog

logger = structlog.get_logger()

CONCEPTS_DIR = os.path.join(OBSIDIAN_DIR, "Knowledge", "Concepts")
SECURITY_DIR = os.path.join(OBSIDIAN_DIR, "Knowledge", "Security")
SNIPPETS_DIR = os.path.join(OBSIDIAN_DIR, "Knowledge", "Snippets")
LOG_PATH = os.path.join(OBSIDIAN_DIR, "Learning_Log.md")

PROMPT = "Напиши безопасный модуль подписи на Rust. Обязательно используй HMAC и библиотеку PyO3 для биндингов."

def setup_knowledge():
    os.makedirs(CONCEPTS_DIR, exist_ok=True)
    os.makedirs(SECURITY_DIR, exist_ok=True)
    os.makedirs(SNIPPETS_DIR, exist_ok=True)

    with open(os.path.join(CONCEPTS_DIR, "PyO3.md"), "w", encoding="utf-8") as f:
        f.write("# PyO3 Rust Bindings\nPyO3 is a library that provides Rust bindings for the Python interpreter. ALWAYS return robust errors wrapped in pyo3::exceptions::PyValueError.")

    with open(os.path.join(SECURITY_DIR, "HMAC_Safety.md"), "w", encoding="utf-8") as f:
        f.write("# HMAC Safety\nWhen computing HMAC signatures in Rust, you must use constant-time equality checks (`subtle::ConstantTimeEq`) to prevent timing attacks.")

    # Insert a fake error in learning log to test Recursive Self-Reflection
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n| Напиши безопасный модуль подписи на Rust | Не использована библиотека subtle | Используй subtle::ConstantTimeEq для проверки |\n")

async def run_test():
    setup_knowledge()
    
    # Clean previous snippets just for test clarity
    for f in os.listdir(SNIPPETS_DIR):
        if f.startswith("Snippet_"):
            os.remove(os.path.join(SNIPPETS_DIR, f))

    executor = PipelineExecutor()
    print("Running v16.1 STRESS TEST for Neural Synthesis...")
    
    result = await executor.execute(PROMPT, brigade="Dmarket-Dev", max_steps=4)
    final_response = result.get("final_response", "")
    
    print("\n--- FINAL PIPELINE RESPONSE ---\n")
    print(final_response)
    print("\n-------------------------------\n")
    
    # 1. Did it find PyO3 and HMAC?
    # Because of the prompt instructions, Researcher should append NotebookLM style citations
    used_pyo3_citation = "PyO3.md" in final_response or "PyO3" in final_response
    used_hmac_citation = "HMAC_Safety.md" in final_response or "HMAC_Safety" in final_response

    # 2. Check Auto Tagging
    snippets = [f for f in os.listdir(SNIPPETS_DIR) if f.startswith("Snippet_")]
    auto_tagged = len(snippets) > 0

    print("--- SUCCESS CRITERIA ---")
    print(f"Synthesized PyO3 Knowledge: {used_pyo3_citation}")
    print(f"Synthesized HMAC Knowledge: {used_hmac_citation}")
    print(f"Auto-tagging triggered (Snippets found {len(snippets)}): {auto_tagged}")
    
    if used_pyo3_citation and used_hmac_citation and auto_tagged:
        print("\n✅ v16.1 STRESS TEST PASSED")
    else:
        print("\n❌ v16.1 STRESS TEST FAILED")

if __name__ == "__main__":
    asyncio.run(run_test())
