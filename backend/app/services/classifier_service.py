"""STUB. Person A replaces this with the real DistilBERT service in week 4.

The interface is fixed: predict(text) -> ClassificationResult. Keep it stable
so the rest of the system does not change when the real model lands.
"""

import random
import time
from dataclasses import dataclass

from app.core.config import settings
from app.models.enums import Category, Sentiment


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


_KEYWORD_RULES: list[tuple[Category, tuple[str, ...]]] = [
    (Category.BILLING, ("charge", "charged", "bill", "payment", "invoice", "emi")),
    (Category.DELIVERY, ("delivery", "shipped", "courier", "parcel", "late", "tracking")),
    (Category.REFUND, ("refund", "return", "money back", "exchange")),
    (Category.PRODUCT_DEFECT, ("broken", "damaged", "defective", "faulty", "not working")),
    (Category.TECHNICAL, ("app", "website", "login", "crash", "error", "otp")),
    (Category.SERVICE_QUALITY, ("rude", "agent", "waiting", "no response", "support")),
]

_NEGATIVE_TERMS = ("terrible", "worst", "angry", "furious", "disgusted", "unacceptable",
                   "never", "cheated", "frustrated", "disappointed", "pathetic")
_POSITIVE_TERMS = ("thanks", "thank you", "great", "appreciate", "helpful", "resolved")


class ClassifierService:
    """Rule-based placeholder so the pipeline is testable from day one."""

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
            category = Category.SERVICE_QUALITY
            confidence = round(random.uniform(0.40, 0.60), 3)

        return ClassificationResult(
            category=category,
            confidence=round(confidence, 3),
            needs_review=confidence < settings.CONFIDENCE_THRESHOLD,
            model_version=self.version,
            inference_ms=int((time.perf_counter() - start) * 1000),
        )


class SentimentService:
    """STUB. Replace with cardiffnlp/twitter-roberta-base-sentiment-latest."""

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


classifier = ClassifierService()
sentiment = SentimentService()
