"""Text normalisation shared by training and inference.

CRITICAL: the backend must import this exact function, not a copy.
Any divergence between training-time and inference-time preprocessing
causes train-serve skew, which degrades accuracy silently.
"""

import re

_REDACTION = re.compile(r"x{2,}", re.IGNORECASE)
_URL = re.compile(r"http\S+")
_LONGNUM = re.compile(r"\d{6,}")
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    text = text.lower().strip()
    text = _REDACTION.sub(" ", text)      # CFPB redaction markers
    text = _URL.sub(" <url> ", text)
    text = _LONGNUM.sub(" <num> ", text)
    return _WS.sub(" ", text).strip()
