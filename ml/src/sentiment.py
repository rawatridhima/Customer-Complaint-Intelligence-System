"""Sentiment scoring for complaints (FR-06), shared by training and inference.

Uses a pretrained model, not fine-tuned. max_length=128 was chosen from
a latency/accuracy experiment: p95 56 ms vs 182 ms at 512 tokens, with
0.987 correlation between the two scores.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MAX_LENGTH = 128
_WS = re.compile(r"\s+")
_REDACTION = re.compile(r"(?i)x{2,}")


def light_clean(text: str) -> str:
    """Keep capitals and punctuation: they carry emotional intensity."""
    return _WS.sub(" ", _REDACTION.sub(" ", text)).strip()


@dataclass(frozen=True)
class SentimentResult:
    label: str           # negative | neutral | positive
    negative_score: float  # 0..1, used by the priority engine
    model_version: str


class SentimentService:
    def __init__(self, model_name: str = MODEL_NAME):
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
        self._labels = [self._model.config.id2label[i].lower()
                        for i in range(self._model.config.num_labels)]
        self.version = model_name.split("/")[-1]

    @torch.inference_mode()
    def score(self, text: str) -> SentimentResult:
        enc = self._tok(light_clean(text), truncation=True,
                        max_length=MAX_LENGTH, return_tensors="pt")
        probs = torch.softmax(self._model(**enc).logits, dim=-1)[0]
        idx = int(probs.argmax())
        return SentimentResult(
            label=self._labels[idx],
            negative_score=round(float(probs[self._labels.index("negative")]), 4),
            model_version=self.version,
        )


@lru_cache(maxsize=1)
def get_sentiment_service() -> SentimentService:
    """Load the model once per process, on first use."""
    return SentimentService()