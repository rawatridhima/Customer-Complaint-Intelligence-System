"""FR-34 emerging-issue rule, chart series, and LLM rate-limit parsing."""

from datetime import date

import httpx
import pytest

from app.core.exceptions import LLMRateLimitedError
from app.services import llm_client
from app.services.analytics_service import (
    BASELINE_DAYS,
    CATEGORIES,
    CURRENT_DAYS,
    detect_emerging,
    fill_series,
)
from app.services.llm_client import OpenAICompatibleClient


def series(baseline_per_day, this_week):
    return [baseline_per_day] * BASELINE_DAYS + list(this_week)


class TestEmerging:
    def test_steady_volume_is_not_emerging(self):
        assert detect_emerging({"mortgage": series(2, [2] * CURRENT_DAYS)}) == []

    def test_a_surge_is_flagged_with_its_numbers(self):
        issues = detect_emerging({"debt_collection": series(1, [6] * CURRENT_DAYS)})
        assert len(issues) == 1
        i = issues[0]
        assert i.category == "debt_collection"
        assert i.last_7_days == 42
        assert i.baseline_mean == 7.0 and i.baseline_sd == 0.0
        assert i.ratio == 6.0

    def test_small_numbers_are_ignored(self):
        # 0 a day for a month, then 3 this week: above the threshold, but noise.
        assert detect_emerging({"mortgage": series(0, [1, 1, 1, 0, 0, 0, 0])}) == []

    def test_a_noisy_baseline_raises_the_bar(self):
        noisy = [0, 6] * (BASELINE_DAYS // 2)  # 7-day windows swing between 18 and 24
        flat_week = [3] * CURRENT_DAYS        # 21: within normal variation
        assert detect_emerging({"cards_and_accounts": noisy + flat_week}) == []

    def test_largest_surge_comes_first(self):
        issues = detect_emerging({
            "mortgage": series(1, [4] * CURRENT_DAYS),
            "debt_collection": series(1, [9] * CURRENT_DAYS),
        })
        assert [i.category for i in issues] == ["debt_collection", "mortgage"]

    def test_wrong_length_is_an_error(self):
        with pytest.raises(ValueError):
            detect_emerging({"mortgage": [1, 2, 3]})


def test_fill_series_has_every_day_and_every_category():
    rows = [(date(2026, 1, 2), "mortgage", 3)]
    out = fill_series(rows, date(2026, 1, 1), date(2026, 1, 4))
    assert [d["date"] for d in out] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert out[1]["mortgage"] == 3 and out[0]["mortgage"] == 0
    assert set(CATEGORIES) <= set(out[0])


# ---- HTTP 429 from the provider --------------------------------------------

def _respond(status, text, resp_headers=None):
    def post(url, headers, json, timeout):
        return httpx.Response(status, text=text, headers=resp_headers or {})
    return post


def test_per_minute_limit_is_retryable_with_the_providers_wait(monkeypatch):
    monkeypatch.setattr(llm_client.httpx, "post",
                        _respond(429, '{"error":"rate"}', {"retry-after": "30"}))
    with pytest.raises(LLMRateLimitedError) as err:
        OpenAICompatibleClient("k", "m").complete("s", "p")
    assert err.value.daily is False and err.value.retry_after == 30


def test_daily_quota_is_recognised(monkeypatch):
    body = '{"error":{"message":"Quota exceeded: GenerateRequestsPerDayPerProjectPerModel"}}'
    monkeypatch.setattr(llm_client.httpx, "post", _respond(429, body))
    with pytest.raises(LLMRateLimitedError) as err:
        OpenAICompatibleClient("k", "m").complete("s", "p")
    assert err.value.daily is True
