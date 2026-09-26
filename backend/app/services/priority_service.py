from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.models.enums import Category, Priority, Sentiment


@dataclass(frozen=True)
class PriorityWeights:
    sentiment: float
    category: float
    urgency: float
    repeat: float

    def __post_init__(self) -> None:
        total = self.sentiment + self.category + self.urgency + self.repeat
        if abs(total - 1.0) > 1e-6:
            raise ConfigurationError(f"weights must sum to 1.0, got {total}")

    @classmethod
    def from_settings(cls) -> "PriorityWeights":
        return cls(
            sentiment=settings.PRIORITY_W_SENTIMENT,
            category=settings.PRIORITY_W_CATEGORY,
            urgency=settings.PRIORITY_W_URGENCY,
            repeat=settings.PRIORITY_W_REPEAT,
        )


@dataclass(frozen=True)
class PriorityResult:
    score: float
    bucket: Priority
    breakdown: dict


class PriorityService:
    """FR-14 to FR-17. Explainable by design. Never a learned model."""

    CATEGORY_SEVERITY: dict[Category, float] = {
        Category.REPORT_MISUSE: 0.85,          # unauthorised pulls; often identity fraud
        Category.MORTGAGE: 0.80,               # foreclosure risk, home at stake
        Category.DEBT_COLLECTION: 0.70,        # harassment, wage garnishment
        Category.CREDIT_REPORT_DISPUTE: 0.60,  # blocks loans, but slower harm
        Category.CONSUMER_LOANS: 0.55,
        Category.CARDS_AND_ACCOUNTS: 0.45,
    }

    URGENCY_TERMS: frozenset[str] = frozenset({
        "urgent", "immediately", "asap", "emergency", "legal", "lawyer",
        "consumer court", "fraud", "unauthorised", "unauthorized",
        "escalate", "third time", "still waiting",
    })

    def __init__(self, weights: PriorityWeights | None = None) -> None:
        self._w = weights or PriorityWeights.from_settings()

    def compute(
        self,
        text: str,
        category: Category,
        sentiment_label: Sentiment,
        sentiment_score: float,
        repeat_count: int = 0,
    ) -> PriorityResult:
        lowered = text.lower()

        s_neg = sentiment_score if sentiment_label is Sentiment.NEGATIVE else 0.0
        c_sev = self.CATEGORY_SEVERITY[category]
        matched = sum(1 for term in self.URGENCY_TERMS if term in lowered)
        u_score = min(matched / 3, 1.0)
        r_flag = min(repeat_count / 2, 1.0)

        factors = {
            "sentiment_negativity": (s_neg, self._w.sentiment),
            "category_severity": (c_sev, self._w.category),
            "urgency_keywords": (u_score, self._w.urgency),
            "repeat_complaint": (r_flag, self._w.repeat),
        }

        breakdown = {
            name: {
                "raw": round(raw, 3),
                "weight": weight,
                "contribution": round(raw * weight, 3),
            }
            for name, (raw, weight) in factors.items()
        }
        score = round(sum(raw * weight for raw, weight in factors.values()), 3)

        return PriorityResult(score=score, bucket=self._bucket(score), breakdown=breakdown)

    @staticmethod
    def _bucket(score: float) -> Priority:
        if score >= 0.80:
            return Priority.P0
        if score >= 0.60:
            return Priority.P1
        if score >= 0.35:
            return Priority.P2
        return Priority.P3
