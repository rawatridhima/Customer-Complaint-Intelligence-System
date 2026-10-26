"""make pregenerate: AI replies generated ahead of a demo."""

import json
import uuid

import pytest

from app.core.exceptions import LLMRateLimitedError
from app.services import llm_service
from app.services.llm_client import LLMResult

pytestmark = pytest.mark.integration


class FakeLLM:
    model = "fake"

    def __init__(self, fail_after=None):
        self.calls = 0
        self.fail_after = fail_after

    def complete(self, system, prompt):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise LLMRateLimitedError("LLM daily quota used up (HTTP 429)", daily=True)
        if "Respond with only a JSON object" in prompt:
            return LLMResult(json.dumps({"summary": "S.", "resolution": "1. Do it.",
                                         "cited_articles": []}), self.model, 10)
        return LLMResult("Dear customer, " + "thank you for your patience. " * 6, self.model, 10)


@pytest.fixture
def open_complaints(client):
    from app.core.database import get_session_factory
    from app.models.complaint import Complaint
    from app.models.enums import AnalysisStatus, Category, Priority, Sentiment
    from app.models.prediction import Prediction

    def _make(n, score=0.99):
        ids = []
        db = get_session_factory()()
        try:
            for _ in range(n):
                cid = uuid.UUID(client.post("/api/v1/complaints", json={
                    "text": f"Urgent pregenerate test complaint {uuid.uuid4().hex}",
                    "customer_ref": f"PG-{uuid.uuid4().hex[:6]}"}).json()["complaint_id"])
                db.add(Prediction(
                    complaint_id=cid, category=Category.MORTGAGE, category_confidence=0.99,
                    sentiment_label=Sentiment.NEGATIVE, sentiment_score=0.9,
                    priority_score=score, priority_bucket=Priority.P0, priority_breakdown={},
                    needs_review=False, model_version="t"))
                db.get(Complaint, cid).analysis_status = AnalysisStatus.COMPLETED
                ids.append(cid)
            db.commit()
        finally:
            db.close()
        return ids

    return _make


def _content(cid):
    from app.core.database import get_session_factory
    from app.repositories.generated_content_repo import GeneratedContentRepository
    db = get_session_factory()()
    try:
        return GeneratedContentRepository(db).get_by_complaint(cid)
    finally:
        db.close()


def test_generates_for_the_most_urgent_first(monkeypatch, open_complaints):
    from app import pregenerate

    # Top score; among equal scores the newest come first, so these two are
    # picked even if earlier runs left other top-scored complaints behind.
    ids = open_complaints(2, score=1.0)
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: FakeLLM())
    done, failed = pregenerate.run(limit=2, include_demo=False, pause=0)
    assert (done, failed) == (2, 0)
    assert all(_content(cid) and not _content(cid).is_fallback for cid in ids)


def test_stops_cleanly_when_the_daily_quota_runs_out(monkeypatch, open_complaints):
    from app import pregenerate

    open_complaints(3, score=1.0)
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: FakeLLM(fail_after=2))
    done, failed = pregenerate.run(limit=3, include_demo=False, pause=0)
    assert done == 1 and failed == 1   # first one ok (2 calls), then quota gone


def test_does_nothing_without_an_llm(monkeypatch):
    from app import pregenerate

    monkeypatch.setattr(llm_service, "get_llm_client", lambda: None)
    assert pregenerate.run(limit=5, include_demo=False, pause=0) == (0, 0)
