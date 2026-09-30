"""FR-19 to FR-25 end to end, with a fake LLM standing in for the provider."""

import json
import uuid

import pytest

from app.core.exceptions import LLMUnavailableError
from app.services import llm_service
from app.services.llm_client import LLMResult

pytestmark = pytest.mark.integration

DRAFT = ("Dear customer, thank you for telling us about the problem with your mortgage "
         "payment. We have opened a review of your escrow account and will send a corrected "
         "statement once it is complete. You will hear from us within five business days. "
         "Customer Support Team")


class FakeLLM:
    """Answers like a well-behaved model and records every prompt it gets."""

    model = "fake-llm"

    def __init__(self, fail=False):
        self.fail = fail
        self.prompts = []

    def complete(self, system, prompt):
        if self.fail:
            raise LLMUnavailableError("LLM timed out after 20s")
        self.prompts.append(prompt)
        if "Respond with only a JSON object" in prompt:
            return LLMResult(json.dumps({
                "summary": "Escrow error doubled the payment. Customer wants it corrected. "
                           "A third sentence that must be removed.",
                "resolution": "1. Acknowledge the notice of error.\n2. Review escrow.",
                "cited_articles": ["KB-1", "KB-7"],
            }), self.model, 50)
        return LLMResult(DRAFT, self.model, 40)


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def analysed_complaint_factory(client):
    from app.core.database import get_session_factory
    from app.models.complaint import Complaint
    from app.models.enums import AnalysisStatus, Category, Priority, Sentiment
    from app.models.prediction import Prediction
    from app.seed import seed_knowledge_base

    db = get_session_factory()()
    seed_knowledge_base(db)
    db.close()

    def _make(text=None, bucket="P1", sentiment="negative", ref=None):
        text = text or ("My mortgage escrow payment doubled because of an escrow shortage "
                        f"error on my statement {uuid.uuid4().hex[:6]}. Please fix it.")
        body = client.post("/api/v1/complaints", json={
            "text": text, "customer_ref": ref or f"L-{uuid.uuid4().hex[:8]}"}).json()
        cid = uuid.UUID(body["complaint_id"])
        db = get_session_factory()()
        try:
            db.add(Prediction(
                complaint_id=cid, category=Category.MORTGAGE, category_confidence=0.97,
                sentiment_label=Sentiment(sentiment), sentiment_score=0.8,
                priority_score=0.7, priority_bucket=Priority(bucket),
                priority_breakdown={}, needs_review=False, model_version="test",
            ))
            db.get(Complaint, cid).analysis_status = AnalysisStatus.COMPLETED
            db.commit()
        finally:
            db.close()
        return str(cid)

    return _make


def _generate(client, headers, cid, tone=None):
    body = {"tone": tone} if tone else None
    return client.post(f"/api/v1/complaints/{cid}/generated-content", headers=headers, json=body)


def test_generates_summary_resolution_and_draft_with_citations(
        client, auth_headers, fake_llm, analysed_complaint_factory):
    headers = auth_headers("agent")
    cid = analysed_complaint_factory()

    resp = _generate(client, headers, cid)
    assert resp.status_code == 200, resp.text
    c = resp.json()
    assert c["is_fallback"] is False
    assert c["summary"].count(".") == 2          # FR-19: third sentence cut
    assert c["draft_response"] == DRAFT
    assert c["tone"] == "empathetic"             # FR-21: negative, P1
    assert c["llm_model"] == "fake-llm" and c["token_count"] == 90
    # FR-20: KB-1 was a real mortgage article; KB-7 was invented and dropped.
    assert len(c["cited_articles"]) == 1
    assert "escrow" in c["cited_articles"][0]["title"].lower()

    prompt = fake_llm.prompts[0]
    assert "[KB-1]" in prompt and "category: mortgage" in prompt


def test_only_redacted_text_reaches_the_llm(client, auth_headers, fake_llm, analysed_complaint_factory):
    """FR-06, C-03."""
    cid = analysed_complaint_factory(
        text="Escrow error on my mortgage. Email me at jane.doe@example.com or call 555-123-4567.")
    _generate(client, auth_headers("agent"), cid)
    joined = "\n".join(fake_llm.prompts)
    assert "jane.doe@example.com" not in joined
    assert "555-123-4567" not in joined


def test_p0_gets_the_urgent_tone(client, auth_headers, fake_llm, analysed_complaint_factory):
    cid = analysed_complaint_factory(bucket="P0")
    assert _generate(client, auth_headers("agent"), cid).json()["tone"] == "urgent"


def test_agent_can_regenerate_in_another_tone(client, auth_headers, fake_llm, analysed_complaint_factory):
    headers = auth_headers("agent")
    cid = analysed_complaint_factory()
    _generate(client, headers, cid)
    c = _generate(client, headers, cid, tone="professional").json()
    assert c["tone"] == "professional"
    history = client.get(f"/api/v1/complaints/{cid}/history", headers=headers).json()
    assert history[0]["action"] == "response_regenerated"


def test_identical_text_reuses_cached_content(client, auth_headers, fake_llm, analysed_complaint_factory):
    """FR-24."""
    headers = auth_headers("agent")
    text = f"Duplicate escrow complaint text for caching {uuid.uuid4().hex}."
    first = analysed_complaint_factory(text=text)
    second = analysed_complaint_factory(text=text)
    _generate(client, headers, first)
    calls_before = len(fake_llm.prompts)

    c = _generate(client, headers, second).json()
    assert len(fake_llm.prompts) == calls_before   # no new LLM call
    assert c["token_count"] == 0
    assert c["draft_response"] == DRAFT


def test_llm_failure_saves_the_template_and_flags_it(
        client, auth_headers, monkeypatch, analysed_complaint_factory):
    """FR-25, NFR-07."""
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: FakeLLM(fail=True))
    cid = analysed_complaint_factory()
    resp = _generate(client, auth_headers("agent"), cid)
    assert resp.status_code == 200
    c = resp.json()
    assert c["is_fallback"] is True
    assert "timed out" in c["fallback_reason"]
    assert c["draft_response"].startswith("Dear customer")
    assert c["summary"] is None


def test_no_llm_configured_also_falls_back(client, auth_headers, monkeypatch, analysed_complaint_factory):
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: None)
    c = _generate(client, auth_headers("agent"), analysed_complaint_factory()).json()
    assert c["is_fallback"] is True


def test_edit_keeps_the_generated_draft(client, auth_headers, fake_llm, analysed_complaint_factory):
    """FR-23."""
    headers = auth_headers("agent")
    cid = analysed_complaint_factory()
    _generate(client, headers, cid)
    c = client.patch(f"/api/v1/complaints/{cid}/generated-content", headers=headers,
                     json={"final_response": "Edited reply text."}).json()
    assert c["final_response"] == "Edited reply text."
    assert c["draft_response"] == DRAFT
    assert c["was_edited"] is True


def test_approval_records_who_and_locks_the_content(client, auth_headers, fake_llm, analysed_complaint_factory):
    """FR-22, FR-30."""
    headers = auth_headers("agent")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    cid = analysed_complaint_factory()
    _generate(client, headers, cid)

    c = client.post(f"/api/v1/complaints/{cid}/generated-content/approve", headers=headers,
                    json={"final_response": DRAFT}).json()
    assert c["approved_by"] == me["user_id"] and c["approved_at"]
    assert c["was_edited"] is False

    assert client.patch(f"/api/v1/complaints/{cid}/generated-content", headers=headers,
                        json={"final_response": "late edit"}).status_code == 409
    assert _generate(client, headers, cid).status_code == 409
    assert client.post(f"/api/v1/complaints/{cid}/generated-content/approve", headers=headers,
                       json={"final_response": "again"}).status_code == 409

    history = client.get(f"/api/v1/complaints/{cid}/history", headers=headers).json()
    assert history[0]["action"] == "response_approved"


def test_content_is_404_until_generated(client, auth_headers, analysed_complaint_factory):
    cid = analysed_complaint_factory()
    resp = client.get(f"/api/v1/complaints/{cid}/generated-content", headers=auth_headers("agent"))
    assert resp.status_code == 404


def test_unknown_tone_is_rejected(client, auth_headers, fake_llm, analysed_complaint_factory):
    resp = _generate(client, auth_headers("agent"), analysed_complaint_factory(), tone="sarcastic")
    assert resp.status_code == 422


def test_worker_task_retries_then_falls_back(monkeypatch, analysed_complaint_factory):
    """NFR-08: the worker retries a failing LLM and only falls back on the last try."""
    from app.workers import tasks

    monkeypatch.setattr(llm_service, "get_llm_client", lambda: FakeLLM(fail=True))
    cid = analysed_complaint_factory()

    class Retry(Exception):
        pass

    retries = []
    task = tasks.generate_complaint_content

    def fake_retry(exc=None, countdown=None):
        retries.append(countdown)
        return Retry()

    monkeypatch.setattr(task, "retry", fake_retry)

    for attempt in range(task.max_retries):
        task.request.retries = attempt
        with pytest.raises(Retry):
            task.run(cid)

    task.request.retries = task.max_retries  # the last attempt
    task.run(cid)
    task.request.retries = 0

    from app.core.database import get_session_factory
    from app.services.generated_content_service import GeneratedContentService
    content = GeneratedContentService(get_session_factory()()).get(uuid.UUID(cid))
    assert content.is_fallback is True
    assert retries == [10, 20, 40]   # exponential backoff
