import hashlib
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?\b\d{10}\b")
_ACCOUNT = re.compile(r"\b\d{12,19}\b")
# A run of digits broken up by spaces, dashes, dots or brackets, as people
# write phone and card numbers: 555-123-4567, (555) 123 4567, +91 98765 43210,
# 4111 1111 1111 1111. Classified by how many digits it holds (_grouped).
# A "$" or letter just before it (amounts, IDs) and slashes (dates) never match.
_GROUPED_NUMBER = re.compile(r"(?<![\w$.,])\+?\(?\d[\d \t().-]{7,}\d(?![\w])")
_WHITESPACE = re.compile(r"\s+")


class RedactionService:
    """FR-06, NFR-12. Nothing leaves the system boundary un-redacted."""

    def redact(self, text: str) -> str:
        text = _ACCOUNT.sub("<account>", text)
        text = _EMAIL.sub("<email>", text)
        text = _GROUPED_NUMBER.sub(_grouped, text)
        text = _PHONE.sub("<phone>", text)
        return text

    def hash_text(self, text: str) -> str:
        """Normalised hash. Used for dedupe (FR-05) and LLM cache (FR-24)."""
        normalised = _WHITESPACE.sub(" ", text.lower().strip())
        return hashlib.sha256(normalised.encode()).hexdigest()


def _grouped(match: re.Match) -> str:
    digits = sum(ch.isdigit() for ch in match.group())
    if 13 <= digits <= 19:
        return "<account>"  # card and account numbers
    if 10 <= digits <= 12:
        return "<phone>"    # national and international phone numbers
    return match.group()    # dates, amounts, short references: keep
