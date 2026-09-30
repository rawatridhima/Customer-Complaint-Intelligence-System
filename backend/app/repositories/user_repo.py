import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Database access for users."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        return user

    def get(self, user_id: uuid.UUID) -> User | None:
        return self._db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return self._db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return self._db.execute(stmt).scalar_one_or_none()

    def list(self) -> list[User]:
        stmt = select(User).order_by(User.created_at)
        return list(self._db.execute(stmt).scalars().all())

    def commit(self) -> None:
        self._db.commit()
