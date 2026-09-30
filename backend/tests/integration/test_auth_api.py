"""FR-37 to FR-40: login, tokens and role-based access, end to end."""

import uuid

import pytest

pytestmark = pytest.mark.integration


# ---- login (FR-37) ---------------------------------------------------------

def test_login_returns_token_and_user(client, demo_users):
    resp = client.post("/api/v1/auth/login",
                       json={"username": "agent", "password": demo_users["agent"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "agent"
    assert "password_hash" not in body["user"]


def test_username_is_case_insensitive(client, demo_users):
    resp = client.post("/api/v1/auth/login",
                       json={"username": "AGENT", "password": demo_users["agent"]})
    assert resp.status_code == 200


@pytest.mark.parametrize("username,password", [
    ("agent", "wrong-password"),
    ("nobody-by-this-name", "whatever-password"),
])
def test_bad_login_gives_one_generic_message(client, demo_users, username, password):
    resp = client.post("/api/v1/auth/login",
                       json={"username": username, "password": password})
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Incorrect username or password"


def test_me_returns_the_signed_in_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers("manager"))
    assert resp.status_code == 200
    assert resp.json()["username"] == "manager"


# ---- tokens (FR-40) ----------------------------------------------------------

def test_protected_route_without_token_is_401(client):
    assert client.get("/api/v1/complaints").status_code == 401


def test_protected_route_with_bad_token_is_401(client):
    resp = client.get("/api/v1/complaints",
                      headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_complaint_submission_stays_public(client):
    resp = client.post("/api/v1/complaints", json={
        "text": "Public intake must work without an account, like a web form.",
        "customer_ref": "PUBLIC-1",
    })
    assert resp.status_code == 201


def test_staff_can_list_complaints(client, auth_headers):
    resp = client.get("/api/v1/complaints", headers=auth_headers("agent"))
    assert resp.status_code == 200


# ---- roles (FR-38, FR-39) ------------------------------------------------------

@pytest.mark.parametrize("username", ["agent", "manager"])
def test_only_admins_manage_users(client, auth_headers, username):
    assert client.get("/api/v1/users", headers=auth_headers(username)).status_code == 403


def test_admin_creates_user_who_can_then_log_in(client, auth_headers):
    name = f"agent_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/users", headers=auth_headers("admin"), json={
        "username": name, "email": f"{name}@example.com",
        "password": "a-good-password", "role": "agent",
    })
    assert resp.status_code == 201, resp.text

    login = client.post("/api/v1/auth/login",
                        json={"username": name, "password": "a-good-password"})
    assert login.status_code == 200


def test_deactivated_user_is_locked_out_immediately(client, auth_headers):
    admin = auth_headers("admin")
    name = f"temp_{uuid.uuid4().hex[:8]}"
    user_id = client.post("/api/v1/users", headers=admin, json={
        "username": name, "email": f"{name}@example.com", "password": "a-good-password",
    }).json()["user_id"]
    token = client.post("/api/v1/auth/login",
                        json={"username": name, "password": "a-good-password"}
                        ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    client.patch(f"/api/v1/users/{user_id}", headers=admin, json={"is_active": False})

    # The token has not expired, but the account is disabled.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_admin_cannot_demote_themselves(client, auth_headers):
    admin = auth_headers("admin")
    me = client.get("/api/v1/auth/me", headers=admin).json()
    resp = client.patch(f"/api/v1/users/{me['user_id']}", headers=admin,
                        json={"role": "agent"})
    assert resp.status_code == 422


def test_duplicate_username_is_rejected(client, auth_headers):
    resp = client.post("/api/v1/users", headers=auth_headers("admin"), json={
        "username": "agent", "email": "someone-else@example.com",
        "password": "a-good-password",
    })
    assert resp.status_code == 422


def test_agent_cannot_create_knowledge_articles(client, auth_headers):
    resp = client.post("/api/v1/knowledge-articles", headers=auth_headers("agent"), json={
        "title": "t", "body": "b", "category": "mortgage",
    })
    assert resp.status_code == 403


# ---- identity comes from the token, not the request body -------------------------

def test_feedback_is_attributed_to_the_signed_in_user(client, auth_headers):
    headers = auth_headers("agent")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    complaint = client.post("/api/v1/complaints", json={
        "text": "My mortgage servicer lost my payment and charged a late fee.",
        "customer_ref": f"FB-{uuid.uuid4().hex[:6]}",
    }).json()

    resp = client.post("/api/v1/feedback", headers=headers, json={
        "complaint_id": complaint["complaint_id"],
        "field_corrected": "category",
        "original_value": "debt_collection",
        "corrected_value": "mortgage",
        "model_version": "distilbert-v1-512",
        "corrected_by": str(uuid.uuid4()),  # an attempt to impersonate is ignored
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["corrected_by"] == me["user_id"]
