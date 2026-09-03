import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Requires the database to be reachable. Run via: make test"""
    from app.main import app

    with TestClient(app) as c:
        yield c
