"""
Obsidian Logic Integration for OpenClaw v16.0
Reads configuration, logic overrides, and dynamic instructions from .obsidian vault.
Records learning logs directly back into Obsidian for Self-Teaching.
"""

import os
import re
import structlog
from typing import Optional, List, Tuple

try:
    import json
except ImportError:
    import json

logger = structlog.get_logger("LogicProvider")

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBSIDIAN_DIR = os.path.join(_project_root, ".obsidian")
CLAW_LOGIC_DIR = os.path.join(OBSIDIAN_DIR, "claw_logic")
LEARNING_LOG_PATH = os.path.join(OBSIDIAN_DIR, "Learning_Log.md")

def _ensure_dirs():
    os.makedirs(CLAW_LOGIC_DIR, exist_ok=True)

def get_brigade_logic(brigade_name: str) -> str:
    """Read brigade's custom logic from .obsidian/claw_logic/<brigade_name>.md."""
    _ensure_dirs()
    path = os.path.join(CLAW_LOGIC_DIR, f"{brigade_name}.md")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                logger.info("Loaded custom brigade logic from Obsidian", brigade=brigade_name)
                return f"\n\n[OBSIDIAN BRIGADE LOGIC ({brigade_name})]\n{content}\n"
        except Exception as e:
            logger.warning("Failed to read Obsidian brigade logic", error=str(e), brigade=brigade_name)
    return ""

def record_learning(task: str, error: str, fix: str):
    """Append a learning entry to Learning_Log.md as a Markdown table row."""
    _ensure_dirs()
    try:
        # One line markdown strip
        task_clean = task.replace('\n', ' ').replace('|', '\\|')[:200]
        error_clean = error.replace('\n', ' ').replace('|', '\\|')[:500] if error else "Success"
        fix_clean = fix.replace('\n', ' ').replace('|', '\\|')[:500]
        
        row = f"| {task_clean} | {error_clean} | {fix_clean} |\n"
        
        # Write header if file doesn't exist or is empty
        is_new = not os.path.exists(LEARNING_LOG_PATH) or os.path.getsize(LEARNING_LOG_PATH) == 0
        
        with open(LEARNING_LOG_PATH, "a", encoding="utf-8") as f:
            if is_new:
                f.write("| Task | Error | Fix / Insight |\n")
                f.write("|---|---|---|\n")
            f.write(row)
            
        logger.info("Recorded learning log to Obsidian", task=task_clean)
    except Exception as e:
        logger.error("Failed to append to Learning_Log.md", error=str(e))

def get_instruction_override(prompt: str) -> Tuple[Optional[List[str]], str]:
    """
    Search for dynamic instructions with #instruction tag in Claw_Logic. 
    If keywords match the prompt, return a custom chain and the instruction details.
    """
    _ensure_dirs()
    matched_instructions = []
    custom_chain = None
    
    prompt_lower = prompt.lower()
    
    for filename in os.listdir(CLAW_LOGIC_DIR):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(CLAW_LOGIC_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Match `#instruction [kw1, kw2]`
            match = re.search(r'#instruction\s*\[(.*?)\]', content, re.IGNORECASE)
            if match:
                keywords = [k.strip().lower() for k in match.group(1).split(',')]
                # Check if any keyword is in the prompt
                if any(kw in prompt_lower for kw in keywords if kw):
                    matched_instructions.append(f"Source [{filename}]:\n{content}")
                    
                    # Look for `chain: ["Planner", "Coder"]`
                    chain_match = re.search(r'chain:\s*(\[.*?\])', content, re.IGNORECASE|re.DOTALL)
                    if chain_match and not custom_chain:
                        try:
                            # Reformat string to strictly parse json or ast if needed
                            # Assuming basic `["Planner", "Coder"]`
                            tmp_chain = json.loads(chain_match.group(1))
                            if isinstance(tmp_chain, list):
                                custom_chain = tmp_chain
                                logger.info("Found custom chain override via Obsidian instruction", chain=custom_chain, file=filename)
                        except Exception:
                            logger.warning("Failed to parse custom chain JSON", file=filename)
                            
        except Exception as e:
            logger.warning("Failed to process instruction file", error=str(e), file=filename)
            
    if matched_instructions:
        return custom_chain, "\n\n[OBSIDIAN OVERRIDE INSTRUCTIONS]\n" + "\n\n".join(matched_instructions)
    return None, ""

def _tokenize(text: str) -> set:
    words = re.findall(r'\w+', text.lower())
    return set(w for w in words if len(w) > 3)

def get_neural_connection(prompt: str) -> str:
    """Implement GraphRAG/Semantic Cross-Linking natively to jump through graph."""
    _ensure_dirs()
    obsidian_root = OBSIDIAN_DIR
    if not os.path.exists(obsidian_root):
        return ""
    
    prompt_tokens = _tokenize(prompt)
    if not prompt_tokens:
        return ""
    
    best_matches = []
    for root_dir, dirs, files in os.walk(obsidian_root):
        # Exclude internal logic directories and git
        if "claw_logic" in root_dir or ".git" in root_dir:
            continue
        for f in files:
            if not f.endswith(".md"): continue
            if f == "Learning_Log.md": continue
            
            fpath = os.path.join(root_dir, f)
            try:
                with open(fpath, "r", encoding="utf-8") as file_obj:
                    content = file_obj.read()
                    
                title_tokens = _tokenize(f)
                content_tokens = _tokenize(content)
                
                # Title matches are weighted heavily (to find "PyO3", "HMAC")
                score = len(prompt_tokens.intersection(title_tokens)) * 5.0
                score += len(prompt_tokens.intersection(content_tokens)) * 0.5
                
                # Only include if score is decent
                if score >= 2.0:
                    rel_path = os.path.relpath(fpath, obsidian_root)
                    best_matches.append((score, f, rel_path, content))
            except Exception:
                pass

    best_matches.sort(key=lambda x: x[0], reverse=True)
    top_matches = best_matches[:2] # Top 2 matches
    
    if top_matches:
        parts = []
        for score, title, rel, content in top_matches:
            logger.info("Semantic Cross-Linking found Note", note=title, score=score)
            snippet = content[:800] # trunc
            # Provide exact anchor/doc source so Citation Grounding can pick it up
            parts.append(f"## {title}\n(Source: {rel})\n{snippet}")
        
        return "\n\n[NEURAL CONNECTION: СВЯЗАННЫЕ ЗНАНИЯ ИЗ OBSIDIAN]\n" + "\n\n---\n\n".join(parts) + "\n"
    return ""

def check_learning_log(prompt: str) -> str:
    """Read last 10 entries of Learning_Log.md. If prompt is similar to an error entry, return instruction."""
    if not os.path.exists(LEARNING_LOG_PATH):
        return ""
        
    prompt_tokens = _tokenize(prompt)
    if not prompt_tokens:
        return ""
        
    try:
        with open(LEARNING_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        data_lines = [line for line in lines if line.strip() and not line.startswith("|---") and not line.startswith("| Task")]
        last_10 = data_lines[-10:]
        
        for line in reversed(last_10):
            cols = [c.strip() for c in line.split("|") if c.strip()]
            if len(cols) >= 3:
                task, error, fix = cols[0], cols[1], cols[2]
                
                task_tokens = _tokenize(task)
                overlap = len(prompt_tokens.intersection(task_tokens))
                
                # If high overlap and not a generic success
                if overlap >= max(2, len(prompt_tokens)*0.3) and "Success" not in error:
                    logger.info("Recursive Self-Reflection triggered", match=task)
                    return f"\n\n[RECURSIVE SELF-REFLECTION]\nВ прошлый раз ты ошибся здесь: {error}\nИсправь это сразу: {fix}\n"
    except Exception as e:
        logger.warning("Failed to check Learning Log", error=str(e))
        
    return ""

def auto_tag_snippet(task: str, code: str):
    """Automatically save successful code to .obsidian/Knowledge/Snippets/."""
    try:
        import uuid
        if not code or len(code) < 20: return
        
        # Determine if code logic executed
        is_code = "rust" in task.lower() or "python" in task.lower() or "код" in task.lower()
        if not is_code and "```" not in code:
            return
            
        snippets_dir = os.path.join(OBSIDIAN_DIR, "Knowledge", "Snippets")
        os.makedirs(snippets_dir, exist_ok=True)
        
        tokens = _tokenize(task)
        tags = " ".join([f"#{t}" for t in tokens if len(t) > 3][:5])
        
        snippet_id = uuid.uuid4().hex[:8]
        filepath = os.path.join(snippets_dir, f"Snippet_{snippet_id}.md")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Task: {task}\nTags: {tags}\n\n{code}")
            
        logger.info("Dynamic Auto-Tagging saved snippet", snippet_id=snippet_id, path=filepath)
    except Exception as e:
        logger.error("Auto-tagging failed", error=str(e))
