"""ML inference services: category classification (FR-08) and sentiment (FR-06).

Loads the fine-tuned DistilBERT model from settings.MODEL_DIR and the
pretrained sentiment model from Hugging Face. If either is unavailable
(CI, a teammate without the model files, torch not installed) the
rule-based stub is used instead, so the pipeline always works.

The public interface is unchanged:
    classifier.predict(text) -> ClassificationResult
    sentiment.predict(text)  -> SentimentResult
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.models.enums import Category, Sentiment

logger = logging.getLogger(__name__)

CLASSIFIER_DIR_NAME = "distilbert-v1-512"
CLASSIFIER_MAX_LENGTH = 512

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
SENTIMENT_MAX_LENGTH = 128


@dataclass(frozen=True)
class ClassificationResult:
    category: Category
    confidence: float
    needs_review: bool
    model_version: str
    inference_ms: int


@dataclass(frozen=True)
class SentimentResult:
    label: Sentiment
    score: float


# --------------------------------------------------------------------------
# Rule-based fallbacks. Used when the real models cannot be loaded.
# --------------------------------------------------------------------------

_KEYWORD_RULES: list[tuple[Category, tuple[str, ...]]] = [
    (Category.REPORT_MISUSE,
     ("inquiry", "inquiries", "hard pull", "unauthorized", "authorize", "breach")),
    (Category.CREDIT_REPORT_DISPUTE,
     ("credit report", "equifax", "experian", "transunion", "dispute", "bureau")),
    (Category.DEBT_COLLECTION,
     ("collection", "collector", "debt", "validation", "owe")),
    (Category.MORTGAGE,
     ("mortgage", "escrow", "foreclosure", "modification", "servicer")),
    (Category.CONSUMER_LOANS,
     ("student loan", "navient", "auto loan", "payday", "personal loan")),
    (Category.CARDS_AND_ACCOUNTS,
     ("credit card", "checking", "savings", "overdraft", "atm", "deposit")),
]

_NEGATIVE_TERMS = ("terrible", "worst", "angry", "furious", "disgusted", "unacceptable",
                   "never", "cheated", "frustrated", "disappointed", "pathetic")
_POSITIVE_TERMS = ("thanks", "thank you", "great", "appreciate", "helpful", "resolved")


class ClassifierService:
    """Rule-based placeholder so the pipeline is testable without model files."""

    version = "stub-v0"

    def predict(self, text: str) -> ClassificationResult:
        start = time.perf_counter()
        lowered = text.lower()

        scores: dict[Category, int] = {}
        for category, terms in _KEYWORD_RULES:
            hits = sum(1 for t in terms if t in lowered)
            if hits:
                scores[category] = hits

        if scores:
            category = max(scores, key=scores.get)
            confidence = min(0.55 + 0.12 * scores[category], 0.97)
        else:
            category = Category.CREDIT_REPORT_DISPUTE
            confidence = round(random.uniform(0.40, 0.60), 3)

        return ClassificationResult(
            category=category,
            confidence=round(confidence, 3),
            needs_review=confidence < settings.CONFIDENCE_THRESHOLD,
            model_version=self.version,
            inference_ms=int((time.perf_counter() - start) * 1000),
        )


class SentimentService:
    """Rule-based placeholder used when the real sentiment model is unavailable."""

    version = "stub-v0"

    def predict(self, text: str) -> SentimentResult:
        lowered = text.lower()
        neg = sum(1 for t in _NEGATIVE_TERMS if t in lowered)
        pos = sum(1 for t in _POSITIVE_TERMS if t in lowered)

        if neg > pos:
            return SentimentResult(Sentiment.NEGATIVE, min(0.60 + 0.10 * neg, 0.98))
        if pos > neg:
            return SentimentResult(Sentiment.POSITIVE, min(0.60 + 0.10 * pos, 0.98))
        return SentimentResult(Sentiment.NEUTRAL, 0.50)


# --------------------------------------------------------------------------
# Real models. torch and transformers are imported lazily so that this module
# still imports in CI, where neither is installed.
# --------------------------------------------------------------------------

class TransformerClassifier:
    """Fine-tuned DistilBERT. Test macro-F1 0.866, p95 ~88 ms on 2 CPU threads."""

    def __init__(self, model_dir: Path) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from preprocess import normalise  # from ml/src, shared with training

        self._torch = torch
        self._normalise = normalise
        self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()
        self._labels = [Category(name)
                        for name in json.loads((model_dir / "labels.json").read_text())]
        self.version = model_dir.name

    def predict(self, text: str) -> ClassificationResult:
        start = time.perf_counter()
        with self._torch.inference_mode():
            encoded = self._tokenizer(
                self._normalise(text),
                truncation=True,
                max_length=CLASSIFIER_MAX_LENGTH,
                return_token_type_ids=False,   # DistilBERT has no segment embeddings
                return_tensors="pt",
            )
            probabilities = self._torch.softmax(self._model(**encoded).logits, dim=-1)[0]

        index = int(probabilities.argmax())
        confidence = float(probabilities[index])

        return ClassificationResult(
            category=self._labels[index],
            confidence=round(confidence, 3),
            needs_review=confidence < settings.CONFIDENCE_THRESHOLD,
            model_version=self.version,
            inference_ms=int((time.perf_counter() - start) * 1000),
        )


class TransformerSentiment:
    """Pretrained RoBERTa, not fine-tuned. 128 tokens: p95 ~56 ms, r=0.987 vs 512."""

    def __init__(self, model_name: str = SENTIMENT_MODEL) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from preprocess import light_clean  # from ml/src, shared with training

        self._torch = torch
        self._light_clean = light_clean
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
        self._labels = [Sentiment(self._model.config.id2label[i].lower())
                        for i in range(self._model.config.num_labels)]
        self.version = model_name.split("/")[-1]

    def predict(self, text: str) -> SentimentResult:
        with self._torch.inference_mode():
            encoded = self._tokenizer(
                self._light_clean(text),
                truncation=True,
                max_length=SENTIMENT_MAX_LENGTH,
                return_token_type_ids=False,
                return_tensors="pt",
            )
            probabilities = self._torch.softmax(self._model(**encoded).logits, dim=-1)[0]

        index = int(probabilities.argmax())
        return SentimentResult(
            label=self._labels[index],
            score=round(float(probabilities[index]), 3),
        )


# --------------------------------------------------------------------------
# Loading. Lazy, and never raises.
#
# Lazy matters: the API process imports this module (via complaint_service ->
# tasks) merely to enqueue a job. Loading at import time would put ~1.5 GB of
# models into a process that never calls predict(). Only the Celery worker
# calls warm() / predict(), so only the worker pays the cost.
#
# Never raises: a missing or corrupt model file falls back to the stub, so
# quality degrades instead of the worker dying.
# --------------------------------------------------------------------------

def _load_classifier() -> ClassifierService | TransformerClassifier:
    model_dir = Path(settings.MODEL_DIR) / CLASSIFIER_DIR_NAME
    if not model_dir.is_dir():
        logger.warning("classifier model not found at %s, using stub", model_dir)
        return ClassifierService()
    try:
        service = TransformerClassifier(model_dir)
        logger.info("loaded classifier %s", service.version)
        return service
    except Exception:
        logger.exception("could not load classifier from %s, using stub", model_dir)
        return ClassifierService()


def _load_sentiment() -> SentimentService | TransformerSentiment:
    try:
        service = TransformerSentiment()
        logger.info("loaded sentiment model %s", service.version)
        return service
    except Exception:
        logger.exception("could not load sentiment model, using stub")
        return SentimentService()


class _LazyService:
    """Defers loading until the first predict() or warm() call."""

    def __init__(self, loader) -> None:
        self._loader = loader
        self._impl = None

    def warm(self):
        """Load now. Called from the Celery worker_process_init signal so the
        first real complaint does not pay the load cost inside its time limit."""
        if self._impl is None:
            self._impl = self._loader()
        return self._impl

    def predict(self, text: str):
        return self.warm().predict(text)

    @property
    def version(self) -> str:
        return self.warm().version


classifier = _LazyService(_load_classifier)
sentiment = _LazyService(_load_sentiment)