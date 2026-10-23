"""Phase 5 end to end: analytics (FR-31 to FR-36), priority weights (FR-17,
FR-39), feedback export (FR-42) and LLM quota handling."""

import csv
import io
import uuid

import pytest

from app.core.exceptions import LLMRateLimitedError
from app.services import llm_service

pytestmark = pytest.mark.integration

WEIGHTS = "/api/v1/settings/priority-weights"


@pytest.fixture
def scored_complaint(client):
    """A complaint with a prediction, as the worker would leave it."""
    from app.core.database import get_session_factory
    from app.models.complaint import Complaint
    from app.models.enums import AnalysisStatus, Category, Priority, Sentiment
    from app.models.prediction import Prediction

    def _make(category="debt_collection", confidence=0.6):
        body = client.post("/api/v1/complaints", json={
            "text": f"A collector keeps calling me about a paid debt {uuid.uuid4().hex[:8]}.",
            "customer_ref": f"A-{uuid.uuid4().hex[:8]}"}).json()
        cid = uuid.UUID(body["complaint_id"])
        db = get_session_factory()()
        try:
            db.add(Prediction(
                complaint_id=cid, category=Category(category), category_confidence=confidence,
                sentiment_label=Sentiment.NEGATIVE, sentiment_score=0.9,
                priority_score=0.5, priority_bucket=Priority.P2, priority_breakdown={},
                needs_review=confidence < 0.95, model_version="test-model"))
            db.get(Complaint, cid).analysis_status = AnalysisStatus.COMPLETED
            db.commit()
        finally:
            db.close()
        return str(cid)

    return _make


@pytest.fixture
def manager(auth_headers):
    return auth_headers("manager")


@pytest.fixture
def default_weights(client, manager):
    """Leave the weights as they were found, whatever the test does."""
    client.delete(WEIGHTS, headers=manager)
    yield
    client.delete(WEIGHTS, headers=manager)


# ---- access ------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/v1/analytics/overview",
    "/api/v1/analytics/model-health",
    WEIGHTS,
    "/api/v1/feedback/export.csv",
])
def test_agents_cannot_see_manager_pages(client, auth_headers, path):
    assert client.get(path, headers=auth_headers("agent")).status_code == 403


# ---- analytics ------------------------------------------------------------------

def test_overview_has_kpis_series_sentiment_and_emerging(client, manager, scored_complaint):
    scored_complaint()
    body = client.get("/api/v1/analytics/overview", headers=manager).json()
    assert {"total", "open", "avg_resolution_hours", "p0"} <= set(body["kpis"])
    assert body["kpis"]["total"] >= 1
    assert len(body["volume"]) == 30                       # default: last 30 days
    assert set(body["sentiment"]) == {"positive", "neutral", "negative"}
    assert set(body["priority"]) == {"P0", "P1", "P2", "P3"}
    assert isinstance(body["emerging"], list)


def test_custom_range_and_validation(client, manager):
    ok = client.get("/api/v1/analytics/overview", headers=manager,
                    params={"date_from": "2026-01-01", "date_to": "2026-01-07"}).json()
    assert len(ok["volume"]) == 7 and ok["range"] == {"from": "2026-01-01", "to": "2026-01-07"}

    backwards = client.get("/api/v1/analytics/overview", headers=manager,
                           params={"date_from": "2026-02-01", "date_to": "2026-01-01"})
    assert backwards.status_code == 422
    too_long = client.get("/api/v1/analytics/overview", headers=manager,
                          params={"date_from": "2024-01-01", "date_to": "2026-01-01"})
    assert too_long.status_code == 422


def test_model_health_reports_threshold_share_and_corrections(
        client, manager, auth_headers, scored_complaint):
    cid = scored_complaint(category="debt_collection", confidence=0.6)
    client.patch(f"/api/v1/complaints/{cid}/category", headers=auth_headers("agent"),
                 json={"category": "mortgage"})

    body = client.get("/api/v1/analytics/model-health", headers=manager).json()
    live = body["live"]
    assert body["threshold"] == 0.95
    assert live["below_threshold"] >= 1 and 0 < live["below_threshold_rate"] <= 1   # FR-36
    assert len(live["confidence_histogram"]) == 10                                # FR-35
    assert any(c["predicted"] == "debt_collection" and c["corrected_to"] == "mortgage"
               for c in live["corrections"])
    assert "llm" in body and "offline" in body


# ---- priority weights (FR-17) ------------------------------------------------------

def test_weights_start_at_the_defaults(client, manager, default_weights):
    body = client.get(WEIGHTS, headers=manager).json()
    assert body["is_custom"] is False
    assert body["weights"] == body["defaults"]
    assert abs(sum(body["weights"].values()) - 1) < 1e-9


def test_weights_must_add_up_to_one(client, manager, default_weights):
    resp = client.put(WEIGHTS, headers=manager, json={
        "weights": {"sentiment": 0.5, "category": 0.5, "urgency": 0.5, "repeat": 0.5}})
    assert resp.status_code == 422


def test_new_weights_score_new_work_and_can_rescore_open_complaints(
        client, manager, auth_headers, scored_complaint, default_weights):
    open_cid = scored_complaint()
    new = {"sentiment": 0.1, "category": 0.7, "urgency": 0.1, "repeat": 0.1}

    body = client.put(WEIGHTS, headers=manager,
                      json={"weights": new, "recalculate_open": True}).json()
    assert body["is_custom"] is True and body["updated_by"] == "manager"
    assert body["weights"] == new and body["rescored"] >= 1

    rescored = client.get(f"/api/v1/complaints/{open_cid}", headers=manager).json()
    assert rescored["prediction"]["priority_breakdown"]["category_severity"]["weight"] == 0.7

    # A category correction now also scores with the new weights.
    cid = scored_complaint(category="debt_collection")
    p = client.patch(f"/api/v1/complaints/{cid}/category", headers=auth_headers("agent"),
                     json={"category": "mortgage"}).json()["prediction"]
    assert p["priority_breakdown"]["sentiment_negativity"]["weight"] == 0.1

    reset = client.delete(WEIGHTS, headers=manager).json()
    assert reset["is_custom"] is False and reset["weights"] == reset["defaults"]


# ---- feedback export (FR-42) -------------------------------------------------------

def test_export_contains_corrections_as_csv(client, manager, auth_headers, scored_complaint):
    cid = scored_complaint(category="debt_collection")
    client.patch(f"/api/v1/complaints/{cid}/category", headers=auth_headers("agent"),
                 json={"category": "consumer_loans"})

    resp = client.get("/api/v1/feedback/export.csv", headers=manager)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    mine = [r for r in rows if r["complaint_id"] == cid]
    assert len(mine) == 1
    assert mine[0]["predicted"] == "debt_collection"
    assert mine[0]["corrected"] == "consumer_loans"
    assert "collector" in mine[0]["text"]


# ---- LLM daily quota -------------------------------------------------------------------

def test_daily_quota_falls_back_at_once_without_retrying(monkeypatch, scored_complaint):
    from app.core.database import get_session_factory
    from app.services.generated_content_service import GeneratedContentService
    from app.workers import tasks

    class QuotaGone:
        model = "fake"

        def complete(self, system, prompt):
            raise LLMRateLimitedError("LLM daily quota used up (HTTP 429)", daily=True)

    monkeypatch.setattr(llm_service, "get_llm_client", lambda: QuotaGone())
    monkeypatch.setattr(tasks.generate_complaint_content, "retry",
                        lambda **k: pytest.fail("should not retry when the daily quota is gone"))
    cid = scored_complaint()

    tasks.generate_complaint_content.request.retries = 0
    tasks.generate_complaint_content.run(cid)

    content = GeneratedContentService(get_session_factory()()).get(uuid.UUID(cid))
    assert content.is_fallback is True
    assert "daily quota" in content.fallback_reason
