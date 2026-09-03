import pytest

pytestmark = pytest.mark.integration


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_rejects_short_text(client):
    resp = client.post("/api/v1/complaints", json={"text": "too short"})
    assert resp.status_code == 422


def test_accepts_valid_complaint(client):
    resp = client.post("/api/v1/complaints", json={
        "text": "I was charged twice for my order last week and nobody has responded.",
        "customer_ref": "TEST-001",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["analysis_status"] == "pending"


def test_duplicate_is_linked(client):
    payload = {
        "text": "The same duplicate complaint text submitted twice in a row here.",
        "customer_ref": "TEST-DUP",
    }
    first = client.post("/api/v1/complaints", json=payload).json()
    second = client.post("/api/v1/complaints", json=payload).json()
    assert second["duplicate_of"] == first["complaint_id"]
