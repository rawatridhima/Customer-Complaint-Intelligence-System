import hashlib
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?\b\d{10}\b")
_ACCOUNT = re.compile(r"\b\d{12,19}\b")
_WHITESPACE = re.compile(r"\s+")


class RedactionService:
    """FR-06, NFR-12. Nothing leaves the system boundary un-redacted."""

    def redact(self, text: str) -> str:
        text = _ACCOUNT.sub("<account>", text)
        text = _EMAIL.sub("<email>", text)
        text = _PHONE.sub("<phone>", text)
        return text

    def hash_text(self, text: str) -> str:
        """Normalised hash. Used for dedupe (FR-05) and LLM cache (FR-24)."""
        normalised = _WHITESPACE.sub(" ", text.lower().strip())
        return hashlib.sha256(normalised.encode()).hexdigest()
