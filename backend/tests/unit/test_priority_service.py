import pytest

from app.core.exceptions import ConfigurationError
from app.models.enums import Category, Priority, Sentiment
from app.services.priority_service import PriorityService, PriorityWeights


@pytest.fixture
def service():
    return PriorityService(PriorityWeights(0.40, 0.25, 0.20, 0.15))


def test_weights_must_sum_to_one():
    with pytest.raises(ConfigurationError):
        PriorityWeights(0.5, 0.5, 0.5, 0.5)


def test_score_is_deterministic(service):
    args = dict(
        text="urgent billing error on my credit card",
        category=Category.CARDS_AND_ACCOUNTS,
        sentiment_label=Sentiment.NEGATIVE,
        sentiment_score=0.9,
        repeat_count=1,
    )
    assert service.compute(**args).score == service.compute(**args).score


def test_score_stays_in_range(service):
    result = service.compute(
        text="urgent emergency fraud legal lawyer escalate immediately",
        category=Category.REPORT_MISUSE,
        sentiment_label=Sentiment.NEGATIVE,
        sentiment_score=1.0,
        repeat_count=10,
    )
    assert 0.0 <= result.score <= 1.0


def test_positive_sentiment_contributes_nothing(service):
    result = service.compute(
        text="thanks for the help",
        category=Category.CONSUMER_LOANS,
        sentiment_label=Sentiment.POSITIVE,
        sentiment_score=0.95,
        repeat_count=0,
    )
    assert result.breakdown["sentiment_negativity"]["contribution"] == 0.0


@pytest.mark.parametrize("score,expected", [
    (0.80, Priority.P0), (0.799, Priority.P1),
    (0.60, Priority.P1), (0.599, Priority.P2),
    (0.35, Priority.P2), (0.349, Priority.P3),
])
def test_bucket_boundaries(score, expected):
    assert PriorityService._bucket(score) is expected


def test_breakdown_sums_to_score(service):
    result = service.compute(
        text="charged twice, still waiting",
        category=Category.CARDS_AND_ACCOUNTS,
        sentiment_label=Sentiment.NEGATIVE,
        sentiment_score=0.8,
        repeat_count=1,
    )
    total = sum(f["contribution"] for f in result.breakdown.values())
    assert abs(total - result.score) < 0.01