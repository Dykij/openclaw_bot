import re
from typing import Optional

class SecurityAuditor:
    """
    Brigade: Dmarket
    Role: Security Auditor
    Model Constraint: llama3.1:8b (8GB VRAM shared)
    
    Scans outputs and logs for hardcoded API keys, environment variables,
    and sensitive tokens before they are saved or broadcasted to Telegram.
    """
    
    # Common patterns for sensitive keys
    PATTERNS = [
        re.compile(r"(?i)(?:api_key|apikey|secret|token|password)[\s:=]+['\"]?([a-zA-Z0-9\-_]{16,})['\"]?"),
        re.compile(r"sk-[a-zA-Z0-9]{32,}"),  # typical OpenAI/generic secret key
        re.compile(r"Bearer\s+[a-zA-Z0-9\-\._~+\/]+=*"), # JWT / Bearer tokens
        re.compile(r"dmarket_[a-zA-Z0-9]{20,}"), # Dmarket specific (mock pattern)
        re.compile(r"[\w-]+\.env") # mentions of .env files being dumped
    ]

    @classmethod
    def scan_for_leaks(cls, text: str) -> bool:
        """
        Scans the text for potential security leaks.
        Returns True if a leak is detected, False otherwise.
        """
        for pattern in cls.PATTERNS:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        Redacts detected sensitive information from the text.
        """
        sanitized_text = text
        for pattern in cls.PATTERNS:
            # Replace the captured group or the whole match with REDACTED
            sanitized_text = pattern.sub("[REDACTED_BY_SECURITY_AUDITOR]", sanitized_text)
        return sanitized_text

# ======= Example Usage =======
if __name__ == "__main__":
    test_log = "Error in connection. Using api_key = 'sk-1234567890abcdef1234567890abcdef12' for retry."
    if SecurityAuditor.scan_for_leaks(test_log):
        print("Leak detected! Sanitizing...")
        safe_log = SecurityAuditor.sanitize(test_log)
        print(f"Safe Log: {safe_log}")
