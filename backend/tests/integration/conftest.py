from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def ensure_test_database() -> None:
    """Create the separate test database if it does not exist yet.

    tests/conftest.py has already pointed DATABASE_URL at it (for example
    cis_test next to cis), so nothing here can touch development data.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    url = make_url(settings.DATABASE_URL)
    assert url.database and url.database.endswith("_test"), (
        f"Refusing to run integration tests against '{url.database}': "
        "the test database name must end in _test")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Bring the test database to the latest schema once per test run.

    Integration tests run the same migrations production does, against their
    own database. Requires a reachable Postgres with pgvector available.
    """
    ensure_test_database()
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def client():
    """Requires the database to be reachable. Run via: make test"""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_users(migrated_database):
    """The three demo accounts from the seed script (idempotent)."""
    from app.core.database import get_session_factory
    from app.seed import DEMO_USERS, seed_users

    db = get_session_factory()()
    try:
        seed_users(db)
    finally:
        db.close()
    return {username: password for username, _, password, _ in DEMO_USERS}


@pytest.fixture
def auth_headers(client, demo_users):
    """auth_headers("manager") -> {"Authorization": "Bearer ..."}"""

    def _headers(username: str) -> dict:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": demo_users[username]},
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _headers
