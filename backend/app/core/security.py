"""Password hashing and JWT tokens (FR-37, FR-40).

Passwords are hashed with bcrypt directly. passlib is not used: its last
release (1.7.4) crashes against bcrypt 5.x, which pip installs by default.

bcrypt only reads the first 72 bytes of a password. Rather than silently
ignoring the rest, longer passwords are rejected at the schema layer
(see MAX_PASSWORD_BYTES) and by hash_password as a backstop.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.exceptions import UnauthorisedError, ValidationError

MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValidationError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("ascii"))
    except ValueError:  # malformed hash in the database
        return False


# A real hash of a random value. Checked against when a username does not
# exist, so a failed login takes the same time whether or not the user exists
# and response timing cannot be used to discover valid usernames.
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise UnauthorisedError("Session expired, please sign in again") from exc
    except JWTError as exc:
        raise UnauthorisedError("Invalid token") from exc
    if not payload.get("sub"):
        raise UnauthorisedError("Invalid token")
    return payload
