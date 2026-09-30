import json
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, UnauthorisedError, ValidationError
from app.core.logging import log_event
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repo import AuditLogRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

# One message for every failure, so a caller cannot tell whether the username
# exists, the password was wrong, or the account is disabled.
_BAD_LOGIN = "Incorrect username or password"


class AuthService:
    """FR-37: username and password login, issuing a signed token."""

    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def login(self, username: str, password: str) -> tuple[str, User]:
        user = self._users.get_by_username(username.strip())

        if user is None:
            verify_password(password, DUMMY_HASH)  # equalise timing
            raise UnauthorisedError(_BAD_LOGIN)
        if not verify_password(password, user.password_hash) or not user.is_active:
            log_event(logger, "login_failed", user_id=str(user.user_id))
            raise UnauthorisedError(_BAD_LOGIN)

        log_event(logger, "login_succeeded", user_id=str(user.user_id), role=user.role)
        return create_access_token(str(user.user_id), user.role.value), user

    def user_from_token_subject(self, subject: str) -> User:
        """Resolve the token's user on every request.

        The role and active flag are read from the database, not trusted from
        the token, so deactivating a user or changing their role takes effect
        immediately rather than when their token expires.
        """
        try:
            user_id = uuid.UUID(subject)
        except ValueError as exc:
            raise UnauthorisedError("Invalid token") from exc
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise UnauthorisedError("Account not found or disabled")
        return user

    @staticmethod
    def token_lifetime_seconds() -> int:
        return settings.JWT_EXPIRY_MINUTES * 60


class UserService:
    """User management, restricted to administrators (FR-39)."""

    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._audit = AuditLogRepository(db)

    def list(self) -> list[User]:
        return self._users.list()

    def get(self, user_id: uuid.UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    def create(self, payload: UserCreate, actor: User) -> User:
        if self._users.get_by_username(payload.username):
            raise ValidationError(f"Username '{payload.username}' is taken")
        if self._users.get_by_email(payload.email):
            raise ValidationError(f"Email '{payload.email}' is already registered")

        user = self._users.add(User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
        ))
        self._record(actor, "user_created", user, {"role": user.role.value})
        self._users.commit()
        return user

    def update(self, user_id: uuid.UUID, payload: UserUpdate, actor: User) -> User:
        user = self.get(user_id)
        changes: dict = {}

        if user.user_id == actor.user_id and (
            payload.is_active is False
            or (payload.role is not None and payload.role != user.role)
        ):
            # Stops the last administrator locking everyone out.
            raise ValidationError("You cannot deactivate or change the role of your own account")

        if payload.role is not None and payload.role != user.role:
            changes["role"] = [user.role.value, payload.role.value]
            user.role = payload.role
        if payload.is_active is not None and payload.is_active != user.is_active:
            changes["is_active"] = [user.is_active, payload.is_active]
            user.is_active = payload.is_active
        if payload.password is not None:
            changes["password"] = "reset"
            user.password_hash = hash_password(payload.password)

        if changes:
            self._record(actor, "user_updated", user, changes)
            self._users.commit()
        return user

    def _record(self, actor: User, action: str, user: User, details: dict) -> None:
        self._audit.add(AuditLog(
            actor_id=actor.user_id,
            action=action,
            entity_type="user",
            entity_id=user.user_id,
            details=json.dumps(details),
        ))
