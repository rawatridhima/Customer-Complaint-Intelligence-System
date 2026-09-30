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


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Bring the test database to the latest schema once per test run.

    The app no longer creates tables on startup, so integration tests run the
    same migrations production does. Requires DATABASE_URL to point at a
    reachable Postgres with the pgvector extension available.
    """
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def client():
    """Requires the database to be reachable. Run via: make test"""
    from app.main import app

    with TestClient(app) as c:
        yield c
