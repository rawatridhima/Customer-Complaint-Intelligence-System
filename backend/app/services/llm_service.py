"""Builds prompts, calls the LLM client, and checks what comes back.

Everything here except the client call is a pure function of its inputs, so
the prompt and parsing logic is unit-tested without any network access. The
network sits behind LLMClient (llm_client.py).

Prompts are versioned files in app/prompts (NFR-22). PROMPT_VERSION picks the
set; changing a prompt means adding a new version, never editing one in place,
so stored content can always be traced to the prompt that produced it.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ConfigurationError, LLMUnavailableError
from app.models.enums import Priority, Sentiment
from app.services.llm_client import LLMClient, get_llm_client

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

SUMMARY_MAX_WORDS = 60      # FR-19
SUMMARY_MAX_SENTENCES = 2   # FR-19
ARTICLE_CHAR_LIMIT = 1500   # per article, keeps the prompt small and fast

TONES = ("urgent", "empathetic", "professional")


@dataclass(frozen=True)
class Article:
    """A knowledge base article as the prompt sees it."""

    label: str   # "KB-1": short, so the model can cite it reliably
    title: str
    body: str


@dataclass
class Analysis:
    summary: str
    resolution: str
    cited_labels: list[str] = field(default_factory=list)
    tokens: int | None = None
    model: str | None = None


# ---- prompt files --------------------------------------------------------------

@lru_cache(maxsize=32)
def load_prompt(name: str, version: str) -> str:
    path = PROMPTS_DIR / f"{name}_{version}.txt"
    if not path.exists():
        raise ConfigurationError(
            f"Prompt file {path.name} not found. Check PROMPT_VERSION in .env "
            f"(files available: {sorted(p.name for p in PROMPTS_DIR.glob(name + '_*'))})"
        )
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def load_tones(version: str) -> dict[str, str]:
    path = PROMPTS_DIR / f"tones_{version}.json"
    if not path.exists():
        raise ConfigurationError(f"Tone file {path.name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ---- pure helpers (unit tested) ------------------------------------------------

def choose_tone(sentiment: Sentiment | None, priority: Priority | None) -> str:
    """FR-21. Tone follows the detected sentiment and priority bucket."""
    if priority is Priority.P0:
        return "urgent"
    if sentiment is Sentiment.NEGATIVE:
        return "empathetic"
    return "professional"


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def enforce_summary_limits(text: str) -> str:
    """FR-19: at most two sentences and 60 words, whatever the model returned.

    The prompt asks for this; this function guarantees it.
    """
    text = " ".join(text.split())
    sentences = _SENTENCE_END.split(text)
    text = " ".join(sentences[:SUMMARY_MAX_SENTENCES])
    words = text.split()
    if len(words) > SUMMARY_MAX_WORDS:
        text = " ".join(words[:SUMMARY_MAX_WORDS]).rstrip(",;:") + "…"
    return text


def format_articles(articles: list[Article]) -> str:
    if not articles:
        return "(No articles match this category. Do not invent a policy; tell the agent what to verify.)"
    blocks = []
    for a in articles:
        body = a.body if len(a.body) <= ARTICLE_CHAR_LIMIT else a.body[:ARTICLE_CHAR_LIMIT] + "…"
        blocks.append(f"[{a.label}] {a.title}\n{body}")
    return "\n\n".join(blocks)


def parse_analysis(raw: str, valid_labels: set[str]) -> Analysis:
    """Pull the JSON object out of the model's reply and validate it.

    Models sometimes wrap JSON in ``` fences or add a sentence before it, so
    this takes the outermost {...}. Anything unusable raises
    LLMUnavailableError, which leads to a retry and then the fallback.
    """
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise LLMUnavailableError("LLM reply contained no JSON object")
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LLMUnavailableError("LLM reply was not valid JSON") from exc
    if not isinstance(data, dict):
        raise LLMUnavailableError("LLM reply JSON was not an object")

    summary = str(data.get("summary") or "").strip()
    resolution = str(data.get("resolution") or "").strip()
    if not summary or not resolution:
        raise LLMUnavailableError("LLM reply was missing the summary or resolution")

    cited = data.get("cited_articles") or []
    if not isinstance(cited, list):
        cited = []
    # Keep only labels we actually gave it: a model can invent "KB-9".
    labels = [c for c in dict.fromkeys(str(c).strip() for c in cited) if c in valid_labels]

    return Analysis(summary=enforce_summary_limits(summary), resolution=resolution,
                    cited_labels=labels)


# ---- service -------------------------------------------------------------------

class LLMService:
    """Generates the summary, suggested resolution and draft response."""

    def __init__(self, client: LLMClient | None = None, prompt_version: str | None = None) -> None:
        self.prompt_version = prompt_version or settings.PROMPT_VERSION
        self._client = client if client is not None else get_llm_client()

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def model(self) -> str | None:
        return self._client.model if self._client else None

    def analyse(
        self,
        complaint_text: str,
        category: str,
        sentiment: str,
        priority: str,
        articles: list[Article],
    ) -> Analysis:
        """FR-19, FR-20. Summary and resolution in one call, to keep latency down."""
        prompt = load_prompt("complaint_analysis", self.prompt_version).format(
            category=category,
            sentiment=sentiment,
            priority=priority,
            articles=format_articles(articles),
            complaint_text=complaint_text,
        )
        result = self._call(prompt)
        analysis = parse_analysis(result.text, {a.label for a in articles})
        analysis.tokens, analysis.model = result.tokens, result.model
        return analysis

    def draft_response(self, complaint_text: str, resolution: str, tone: str) -> tuple[str, int | None]:
        """FR-21. Returns (reply text, tokens used)."""
        tones = load_tones(self.prompt_version)
        if tone not in tones:
            raise ConfigurationError(f"Unknown tone '{tone}'. Choose from: {', '.join(tones)}")
        prompt = load_prompt("draft_response", self.prompt_version).format(
            tone_name=tone,
            tone_guidance=tones[tone],
            resolution=resolution,
            complaint_text=complaint_text,
        )
        result = self._call(prompt)
        text = result.text.strip()
        if len(text.split()) < 20:
            raise LLMUnavailableError("LLM reply was too short to be a customer response")
        return text, result.tokens

    def fallback_response(self) -> str:
        """FR-25. The predefined template used when the LLM cannot be used."""
        return load_prompt("fallback", self.prompt_version).strip()

    def _call(self, prompt: str):
        if self._client is None:
            raise LLMUnavailableError("No LLM is configured (LLM_PROVIDER is empty)")
        return self._client.complete(load_prompt("system", self.prompt_version), prompt)
