"""Refuse to start a production server with development settings.

Called when the API starts. In development it only warns, so local work is
never blocked; with ENVIRONMENT=production a weak secret is a startup error,
because anyone who knows the placeholder can forge an admin login token.
"""

import logging

from sqlalchemy.engine import make_url

from app.core.config import Settings

logger = logging.getLogger(__name__)

PLACEHOLDER_SECRETS = {"dev-only-change-me", "change-me-to-a-long-random-string", ""}
DEFAULT_DB_PASSWORDS = {"cis_password", "postgres", "password", ""}
MIN_SECRET_LENGTH = 32


class UnsafeConfigurationError(RuntimeError):
    pass


def problems(settings: Settings) -> list[str]:
    found = []
    secret = settings.JWT_SECRET.get_secret_value()
    if secret in PLACEHOLDER_SECRETS:
        found.append("JWT_SECRET is the placeholder value")
    elif len(secret) < MIN_SECRET_LENGTH:
        found.append(f"JWT_SECRET is shorter than {MIN_SECRET_LENGTH} characters")
    try:
        password = make_url(settings.DATABASE_URL).password
    except Exception:  # noqa: BLE001 - an unparsable URL fails later, loudly
        password = None
    if password in DEFAULT_DB_PASSWORDS:
        found.append("the database password is a default value")
    return found


def check(settings: Settings) -> None:
    found = problems(settings)
    if not found:
        return
    fix = ('Generate secrets with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"')
    if settings.is_production:
        raise UnsafeConfigurationError(
            "Refusing to start in production: " + "; ".join(found) + ". " + fix)
    for problem in found:
        logger.warning("%s. Fine for local development; set a real value before deploying.", problem)
