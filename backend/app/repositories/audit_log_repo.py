import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    """Database access for audit logs."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, log: AuditLog) -> AuditLog:
        self._db.add(log)
        self._db.flush()
        return log

    def get(
        self,
        audit_id: uuid.UUID,
    ) -> AuditLog | None:
        stmt = select(AuditLog).where(
            AuditLog.audit_id == audit_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def list_by_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
        )

        return list(self._db.execute(stmt).scalars().all())

    def commit(self) -> None:
        self._db.commit()