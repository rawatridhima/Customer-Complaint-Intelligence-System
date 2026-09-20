"""Text normalisation shared by training AND inference.

CRITICAL: the backend must import this exact function, not a copy.
Any divergence between training-time and inference-time preprocessing
causes train-serve skew, which degrades accuracy silently.
"""

import re

_DATE = re.compile(r"\b(?:xx|\d{1,2})/(?:xx|\d{1,2})/(?:xxxx|xx|\d{2,4})\b")
_MONEY = re.compile(r"\{?\$\s*[\d,]*\.?\d+\}?")
_REDACTION = re.compile(r"x{2,}")
_URL = re.compile(r"http\S+")
_LONGNUM = re.compile(r"\d{6,}")
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    text = text.lower().strip()
    text = _DATE.sub(" <date> ", text)       # XX/XX/2018 -> <date>
    text = _MONEY.sub(" <money> ", text)     # {$1,500.00} -> <money>
    text = _REDACTION.sub(" ", text)         # remaining CFPB XXXX markers
    text = _URL.sub(" <url> ", text)
    text = _LONGNUM.sub(" <num> ", text)
    return _WS.sub(" ", text).strip()