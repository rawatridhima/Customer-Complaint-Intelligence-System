"""One complaint through the whole system, as in the demo.

customer submits -> PII redacted -> worker classifies and scores -> worker
asks the LLM -> agent corrects the category -> agent edits and approves the
reply -> agent resolves -> manager sees it in analytics and the export.

The worker tasks are run in-process, with the rule-based classifier and
sentiment stubs and a fake LLM, so the test is fast and needs no model files,
GPU or API key.
"""

import csv
import io
import json
import uuid

import pytest

from app.services import llm_service
from app.services.classifier_service import ClassifierService, SentimentService
from app.services.llm_client import LLMResult

pytestmark = pytest.mark.integration


class FakeLLM:
    model = "fake-llm"

    def __init__(self):
        self.prompts = []

    def complete(self, system, prompt):
        self.prompts.append(prompt)
        if "Respond with only a JSON object" in prompt:
            return LLMResult(json.dumps({
                "summary": "A store card was opened in the customer's name. They want it closed.",
                "resolution": "1. Freeze the account.\n2. Refer to the Fraud team.",
                "cited_articles": ["KB-1"],
            }), self.model, 60)
        return LLMResult("Dear customer, " + "we have frozen the account and opened a fraud case. " * 4
                         + "Customer Support Team", self.model, 40)


@pytest.fixture
def worker(monkeypatch):
    """The two Celery tasks, run in-process with stub models and a fake LLM."""
    from app.workers import tasks

    monkeypatch.setattr(tasks, "classifier", ClassifierService())
    monkeypatch.setattr(tasks, "sentiment", SentimentService())
    fake = FakeLLM()
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: fake)
    queued = []
    monkeypatch.setattr(tasks.generate_complaint_content, "delay", lambda cid: queued.append(cid))
    tasks.generate_complaint_content.request.retries = 0
    return tasks, fake, queued


def test_a_complaint_from_submission_to_resolution(client, auth_headers, worker):
    tasks, llm, queued = worker
    agent, manager = auth_headers("agent"), auth_headers("manager")
    from app.core.database import get_session_factory
    from app.seed import seed_knowledge_base
    seed_knowledge_base(get_session_factory()())

    # 1. A customer submits a complaint, no account needed (FR-01).
    text = ("Someone opened a store card in my name. This is fraud and I need it closed "
            f"immediately. Call me on 555-123-4567. Ref {uuid.uuid4().hex[:6]}")
    created = client.post("/api/v1/complaints", json={"text": text, "customer_ref": "E2E-1"})
    assert created.status_code == 201
    cid = created.json()["complaint_id"]
    assert created.json()["analysis_status"] == "pending"

    # 2. The worker classifies, scores and hands over to the LLM stage.
    tasks.analyse_complaint.run(cid)
    assert queued == [cid]
    detail = client.get(f"/api/v1/complaints/{cid}", headers=agent).json()
    p = detail["prediction"]
    assert detail["analysis_status"] == "completed"
    assert p["model_version"] == "stub-v0"                               # FR-43
    assert set(p["priority_breakdown"]) == {
        "sentiment_negativity", "category_severity", "urgency_keywords", "repeat_complaint"}
    assert p["priority_breakdown"]["urgency_keywords"]["raw"] > 0        # "fraud", "immediately"

    # A redelivered task does not analyse twice.
    tasks.analyse_complaint.run(cid)
    assert queued == [cid]

    # 3. The LLM stage; the phone number never reaches the LLM (FR-06).
    tasks.generate_complaint_content.run(cid)
    content = client.get(f"/api/v1/complaints/{cid}/generated-content", headers=agent).json()
    assert content["is_fallback"] is False and content["summary"]
    assert "555-123-4567" not in "".join(llm.prompts)

    # 4. The agent corrects the category if the stub got it wrong (FR-10).
    if p["category"] != "report_misuse":
        corrected = client.patch(f"/api/v1/complaints/{cid}/category", headers=agent,
                                 json={"category": "report_misuse"}).json()
        assert corrected["prediction"]["category"] == "report_misuse"

    # 5. ...regenerates the reply for the right category, edits and approves it.
    content = client.post(f"/api/v1/complaints/{cid}/generated-content", headers=agent,
                          json={"tone": "urgent"}).json()
    assert content["tone"] == "urgent"
    assert any("identity" in a["title"].lower() or "unauthorised" in a["title"].lower()
               for a in content["cited_articles"])                       # FR-20
    final = content["draft_response"].replace("Dear customer", "Dear Ms Rao")
    approved = client.post(f"/api/v1/complaints/{cid}/generated-content/approve",
                           headers=agent, json={"final_response": final}).json()
    assert approved["approved_at"] and approved["was_edited"] is True   # FR-22, FR-23

    # 6. ...and works the complaint to resolution (FR-28).
    for status in ("in_review", "resolved"):
        assert client.patch(f"/api/v1/complaints/{cid}", headers=agent,
                            json={"status": status}).status_code == 200

    # 7. Every step is in the audit trail, attributed to the agent (FR-30).
    actions = [h["action"] for h in client.get(f"/api/v1/complaints/{cid}/history",
                                               headers=agent).json()]
    assert actions[:4] == ["status_changed", "status_changed", "response_approved",
                           "response_regenerated"]
    assert "category_overridden" in actions or p["category"] == "report_misuse"

    # 8. The manager sees it in analytics and, if corrected, in the export.
    overview = client.get("/api/v1/analytics/overview", headers=manager).json()
    assert overview["kpis"]["resolved"] >= 1
    if p["category"] != "report_misuse":
        rows = list(csv.DictReader(io.StringIO(
            client.get("/api/v1/feedback/export.csv", headers=manager).text)))
        assert any(r["complaint_id"] == cid and r["corrected"] == "report_misuse" for r in rows)


def test_failed_analysis_is_retried_not_lost(client, auth_headers, worker, monkeypatch):
    """NFR-08, NFR-09: a crash during analysis marks the complaint failed and
    asks Celery to retry; the complaint itself is kept."""
    tasks, _, queued = worker

    class Broken:
        def predict(self, text):
            raise RuntimeError("model crashed")

    monkeypatch.setattr(tasks, "classifier", Broken())

    class Retry(Exception):
        pass

    monkeypatch.setattr(tasks.analyse_complaint, "retry", lambda exc=None, **k: Retry())
    cid = client.post("/api/v1/complaints", json={
        "text": "My checking account was charged an overdraft fee I do not owe.",
        "customer_ref": f"E2E-{uuid.uuid4().hex[:6]}"}).json()["complaint_id"]

    agent = auth_headers("agent")
    task = tasks.analyse_complaint

    # Early attempts: still pending, so the inbox shows it is being worked on.
    task.request.retries = 0
    with pytest.raises(Retry):
        task.run(cid)
    assert client.get(f"/api/v1/complaints/{cid}", headers=agent).json()["analysis_status"] == "pending"

    # Last attempt: marked failed, with no half-written prediction left behind.
    task.request.retries = task.max_retries
    with pytest.raises(Retry):
        task.run(cid)
    task.request.retries = 0
    detail = client.get(f"/api/v1/complaints/{cid}", headers=agent).json()
    assert detail["analysis_status"] == "failed"
    assert detail["prediction"] is None
    assert queued == []   # the LLM stage only runs after a successful analysis

    # A later successful run (e.g. after the model is fixed) recovers it.
    monkeypatch.setattr(tasks, "classifier", ClassifierService())
    task.run(cid)
    assert client.get(f"/api/v1/complaints/{cid}", headers=agent).json()["analysis_status"] == "completed"


def test_demo_history_can_be_added_and_removed():
    from app.seed_history import add_history, clear_history

    clear_history()
    assert add_history() > 300
    assert add_history() == 0          # refuses to add twice
    assert clear_history() > 300
