import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repo import AuditLogRepository


class AuditLogService:
    """Business logic for audit logs."""

    def __init__(self, db: Session) -> None:
        self._repo = AuditLogRepository(db)

    def create(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        details: str | None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

        self._repo.add(log)
        self._repo.commit()

        return log

    def get(self, audit_id: uuid.UUID) -> AuditLog:
        log = self._repo.get(audit_id)

        if log is None:
            raise NotFoundError(
                f"Audit log {audit_id} not found"
            )

        return log

    def list_by_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> list[AuditLog]:
        return self._repo.list_by_entity(
            entity_type=entity_type,
            entity_id=entity_id,
        )