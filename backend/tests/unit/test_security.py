"""Password hashing, tokens and role checks. No database needed."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from jose import jwt

from app.api.v1.deps import MANAGERS, require_role
from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorisedError, ValidationError
from app.core.security import (
    MAX_PASSWORD_BYTES,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole


class TestPasswords:
    def test_hash_is_not_the_password_and_verifies(self):
        hashed = hash_password("correct horse battery")
        assert hashed != "correct horse battery"
        assert verify_password("correct horse battery", hashed)

    def test_wrong_password_fails(self):
        assert not verify_password("wrong", hash_password("right-password"))

    def test_same_password_hashes_differently(self):
        assert hash_password("same-password") != hash_password("same-password")

    def test_rejects_passwords_bcrypt_would_truncate(self):
        with pytest.raises(ValidationError):
            hash_password("x" * (MAX_PASSWORD_BYTES + 1))

    def test_overlong_password_never_verifies(self):
        hashed = hash_password("x" * MAX_PASSWORD_BYTES)
        assert not verify_password("x" * (MAX_PASSWORD_BYTES + 1), hashed)

    def test_malformed_hash_is_a_failed_check_not_a_crash(self):
        assert not verify_password("anything", "not-a-bcrypt-hash")


class TestTokens:
    def test_round_trip(self):
        user_id = str(uuid.uuid4())
        payload = decode_access_token(create_access_token(user_id, "agent"))
        assert payload["sub"] == user_id
        assert payload["role"] == "agent"

    def test_expired_token_is_rejected(self):  # FR-40
        past = datetime.now(UTC) - timedelta(minutes=5)
        token = jwt.encode(
            {"sub": "x", "role": "agent", "iat": past - timedelta(hours=1), "exp": past},
            settings.JWT_SECRET.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(UnauthorisedError, match="expired"):
            decode_access_token(token)

    def test_token_signed_with_another_secret_is_rejected(self):
        forged = jwt.encode(
            {"sub": "x", "role": "admin",
             "exp": datetime.now(UTC) + timedelta(hours=1)},
            "attacker-secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(UnauthorisedError):
            decode_access_token(forged)

    def test_garbage_is_rejected(self):
        with pytest.raises(UnauthorisedError):
            decode_access_token("not.a.token")


class TestRoleGuard:  # FR-38
    @staticmethod
    def _user(role):
        return SimpleNamespace(role=role)

    def test_allowed_role_passes_and_returns_the_user(self):
        user = self._user(UserRole.MANAGER)
        assert require_role(*MANAGERS)(user) is user

    def test_admin_counts_as_manager(self):
        require_role(*MANAGERS)(self._user(UserRole.ADMIN))

    def test_other_role_is_forbidden(self):
        with pytest.raises(ForbiddenError):
            require_role(*MANAGERS)(self._user(UserRole.AGENT))
