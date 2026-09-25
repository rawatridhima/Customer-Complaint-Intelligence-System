import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.audit_log import AuditLogCreate, AuditLogOut
from app.services.audit_log_service import AuditLogService

router = APIRouter(
    prefix="/audit-logs",
    tags=["audit-logs"],
)


def get_audit_log_service(
    db: Session = Depends(get_db),
) -> AuditLogService:
    return AuditLogService(db)


@router.post(
    "",
    response_model=AuditLogOut,
    status_code=status.HTTP_201_CREATED,
)
def create_audit_log(
    payload: AuditLogCreate,
    service: AuditLogService = Depends(get_audit_log_service),
):
    return service.create(
        actor_id=payload.actor_id,
        action=payload.action,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        details=payload.details,
    )


@router.get(
    "/{audit_id}",
    response_model=AuditLogOut,
)
def get_audit_log(
    audit_id: uuid.UUID,
    service: AuditLogService = Depends(get_audit_log_service),
):
    return service.get(audit_id)


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=list[AuditLogOut],
)
def list_audit_logs(
    entity_type: str,
    entity_id: uuid.UUID,
    service: AuditLogService = Depends(get_audit_log_service),
):
    return service.list_by_entity(
        entity_type=entity_type,
        entity_id=entity_id,
    )