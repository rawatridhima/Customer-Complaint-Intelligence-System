"""Production refuses to start with development secrets."""

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.production import UnsafeConfigurationError, check, problems

GOOD_SECRET = "x" * 48
GOOD_DB = "postgresql+psycopg://cis:a-long-random-db-password@db:5432/cis"


def make(env="production", secret=GOOD_SECRET, db=GOOD_DB):
    return Settings(ENVIRONMENT=env, JWT_SECRET=SecretStr(secret), DATABASE_URL=db,
                    _env_file=None)


def test_good_production_settings_pass():
    check(make())
    assert problems(make()) == []


@pytest.mark.parametrize("secret,db,expected", [
    ("change-me-to-a-long-random-string", GOOD_DB, "placeholder"),
    ("short", GOOD_DB, "shorter than 32"),
    (GOOD_SECRET, "postgresql+psycopg://cis:cis_password@db:5432/cis", "database password"),
])
def test_unsafe_production_settings_stop_startup(secret, db, expected):
    with pytest.raises(UnsafeConfigurationError, match=expected):
        check(make(secret=secret, db=db))


def test_development_only_warns(monkeypatch):
    from app.core import production

    warnings = []
    monkeypatch.setattr(production.logger, "warning", lambda msg, *args: warnings.append(msg % args))
    check(make(env="development", secret="dev-only-change-me"))   # does not raise
    assert any("placeholder" in w for w in warnings)


def test_cors_origins_are_split_and_can_be_empty():
    assert Settings(CORS_ORIGINS="http://a, http://b", _env_file=None).cors_origins == ["http://a", "http://b"]
    assert Settings(CORS_ORIGINS="", _env_file=None).cors_origins == []
