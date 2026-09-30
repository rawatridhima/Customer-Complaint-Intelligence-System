"""Phase 3: category override, status changes, bulk updates, assignment,
filters and the audit trail (FR-10, FR-26, FR-28 to FR-30, FR-41)."""

import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def analysed_complaint(client):
    """Submit a complaint and attach a prediction, as the worker would."""
    from app.core.database import get_session_factory
    from app.models.enums import AnalysisStatus, Category, Priority, Sentiment
    from app.models.complaint import Complaint
    from app.models.prediction import Prediction

    def _make(category="debt_collection", bucket="P2", score=0.5,
              sentiment="negative", needs_review=True):
        body = client.post("/api/v1/complaints", json={
            "text": "My mortgage company lost my payment and now charges a late fee.",
            "customer_ref": f"T-{uuid.uuid4().hex[:8]}",
        }).json()
        cid = uuid.UUID(body["complaint_id"])
        db = get_session_factory()()
        try:
            db.add(Prediction(
                complaint_id=cid, category=Category(category), category_confidence=0.62,
                sentiment_label=Sentiment(sentiment), sentiment_score=0.8,
                priority_score=score, priority_bucket=Priority(bucket),
                priority_breakdown={}, needs_review=needs_review,
                model_version="test-model",
            ))
            db.get(Complaint, cid).analysis_status = AnalysisStatus.COMPLETED
            db.commit()
        finally:
            db.close()
        return str(cid)

    return _make


# ---- category override (FR-10, FR-41) -------------------------------------

def test_override_changes_category_and_records_who_and_what(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    me = client.get("/api/v1/auth/me", headers=agent).json()
    cid = analysed_complaint(category="debt_collection")

    resp = client.patch(f"/api/v1/complaints/{cid}/category", headers=agent,
                        json={"category": "mortgage"})
    assert resp.status_code == 200, resp.text
    p = resp.json()["prediction"]
    assert p["category"] == "mortgage"
    assert p["original_category"] == "debt_collection"
    assert p["overridden_by"] == me["user_id"]
    assert p["overridden_at"]
    assert p["needs_review"] is False
    # Priority was recomputed with the new category's severity.
    assert set(p["priority_breakdown"]) == {
        "sentiment_negativity", "category_severity", "urgency_keywords", "repeat_complaint"}
    assert p["priority_breakdown"]["category_severity"]["raw"] == 0.8  # mortgage


def test_override_is_saved_as_training_feedback(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    cid = analysed_complaint(category="debt_collection")
    client.patch(f"/api/v1/complaints/{cid}/category", headers=agent, json={"category": "mortgage"})

    rows = client.get(f"/api/v1/feedback/complaint/{cid}", headers=agent).json()
    assert len(rows) == 1
    assert rows[0]["original_value"] == "debt_collection"
    assert rows[0]["corrected_value"] == "mortgage"
    assert rows[0]["model_version"] == "test-model"


def test_second_override_keeps_the_models_original_answer(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    cid = analysed_complaint(category="debt_collection")
    client.patch(f"/api/v1/complaints/{cid}/category", headers=agent, json={"category": "mortgage"})
    p = client.patch(f"/api/v1/complaints/{cid}/category", headers=agent,
                     json={"category": "consumer_loans"}).json()["prediction"]
    assert p["category"] == "consumer_loans"
    assert p["original_category"] == "debt_collection"


def test_override_to_same_category_is_rejected(client, auth_headers, analysed_complaint):
    cid = analysed_complaint(category="mortgage")
    resp = client.patch(f"/api/v1/complaints/{cid}/category", headers=auth_headers("agent"),
                        json={"category": "mortgage"})
    assert resp.status_code == 422


def test_cannot_override_before_analysis(client, auth_headers):
    cid = client.post("/api/v1/complaints", json={
        "text": "Still waiting on analysis for this particular complaint text.",
        "customer_ref": f"T-{uuid.uuid4().hex[:8]}",
    }).json()["complaint_id"]
    resp = client.patch(f"/api/v1/complaints/{cid}/category", headers=auth_headers("agent"),
                        json={"category": "mortgage"})
    assert resp.status_code == 409


# ---- status (FR-28) -------------------------------------------------------------

def test_detail_lists_allowed_next_statuses(client, auth_headers, analysed_complaint):
    cid = analysed_complaint()
    body = client.get(f"/api/v1/complaints/{cid}", headers=auth_headers("agent")).json()
    assert body["status"] == "new"
    assert body["allowed_next_statuses"] == ["escalated", "in_review"]


def test_resolving_sets_resolved_at(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    cid = analysed_complaint()
    client.patch(f"/api/v1/complaints/{cid}", headers=agent, json={"status": "in_review"})
    body = client.patch(f"/api/v1/complaints/{cid}", headers=agent,
                        json={"status": "resolved"}).json()
    assert body["status"] == "resolved"
    assert body["resolved_at"]
    assert body["allowed_next_statuses"] == []


def test_invalid_transition_is_409(client, auth_headers, analysed_complaint):
    cid = analysed_complaint()
    resp = client.patch(f"/api/v1/complaints/{cid}", headers=auth_headers("agent"),
                        json={"status": "resolved"})  # new -> resolved is not allowed
    assert resp.status_code == 409


# ---- bulk (FR-29) -----------------------------------------------------------------

def test_bulk_update_reports_successes_and_failures_separately(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    a, b, c = analysed_complaint(), analysed_complaint(), analysed_complaint()
    # c is already resolved, so it cannot move to in_review
    client.patch(f"/api/v1/complaints/{c}", headers=agent, json={"status": "in_review"})
    client.patch(f"/api/v1/complaints/{c}", headers=agent, json={"status": "resolved"})
    missing = str(uuid.uuid4())

    resp = client.patch("/api/v1/complaints/bulk-status", headers=agent, json={
        "complaint_ids": [a, b, c, missing, a], "status": "in_review",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["updated"]) == sorted([a, b])
    failed = {f["complaint_id"]: f["reason"] for f in body["failed"]}
    assert set(failed) == {c, missing}
    assert "resolved" in failed[c]


def test_bulk_needs_at_least_one_id(client, auth_headers):
    resp = client.patch("/api/v1/complaints/bulk-status", headers=auth_headers("agent"),
                        json={"complaint_ids": [], "status": "in_review"})
    assert resp.status_code == 422


# ---- assignment and filters (FR-26) ----------------------------------------------

def test_assign_to_me_and_filter(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    me = client.get("/api/v1/auth/me", headers=agent).json()
    cid = analysed_complaint()

    body = client.patch(f"/api/v1/complaints/{cid}/assignee", headers=agent,
                        json={"user_id": me["user_id"]}).json()
    assert body["assigned_to"] == me["user_id"]

    mine = client.get("/api/v1/complaints", headers=agent,
                      params={"assigned": "me", "size": 100}).json()
    assert cid in [c["complaint_id"] for c in mine["items"]]
    unassigned = client.get("/api/v1/complaints", headers=agent,
                            params={"assigned": "none", "size": 100}).json()
    assert cid not in [c["complaint_id"] for c in unassigned["items"]]


def test_filter_by_sentiment_and_sort_by_priority(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    low = analysed_complaint(bucket="P3", score=0.10, sentiment="neutral")
    high = analysed_complaint(bucket="P0", score=0.99, sentiment="neutral")

    items = client.get("/api/v1/complaints", headers=agent, params={
        "sentiment": "neutral", "sort": "priority", "size": 100,
    }).json()["items"]
    ids = [c["complaint_id"] for c in items]
    assert ids.index(high) < ids.index(low)
    assert all(c["prediction"]["sentiment_label"] == "neutral" for c in items)


def test_date_range_must_be_ordered(client, auth_headers):
    resp = client.get("/api/v1/complaints", headers=auth_headers("agent"),
                      params={"date_from": "2026-02-01", "date_to": "2026-01-01"})
    assert resp.status_code == 422


# ---- audit trail (FR-30) -----------------------------------------------------------

def test_history_records_every_action_with_the_user(client, auth_headers, analysed_complaint):
    agent = auth_headers("agent")
    cid = analysed_complaint(category="debt_collection")
    client.patch(f"/api/v1/complaints/{cid}/category", headers=agent, json={"category": "mortgage"})
    client.patch(f"/api/v1/complaints/{cid}", headers=agent, json={"status": "in_review"})

    history = client.get(f"/api/v1/complaints/{cid}/history", headers=agent).json()
    assert [h["action"] for h in history] == ["status_changed", "category_overridden"]
    assert all(h["actor_username"] == "agent" for h in history)
    assert history[0]["details"] == {"from": "new", "to": "in_review"}
    assert history[1]["details"]["from"] == "debt_collection"
