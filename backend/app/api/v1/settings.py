from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import ManagerUser
from app.core.database import get_db
from app.schemas.settings import PriorityWeightsOut, PriorityWeightsUpdate
from app.services.settings_service import SettingsService

# FR-17, FR-39: priority weights are configured by managers (and administrators).
router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(db)


@router.get("/priority-weights", response_model=PriorityWeightsOut)
def get_priority_weights(
    user: ManagerUser,
    service: SettingsService = Depends(get_settings_service),
):
    return service.priority_weights_view()


@router.put("/priority-weights", response_model=PriorityWeightsOut)
def set_priority_weights(
    payload: PriorityWeightsUpdate,
    user: ManagerUser,
    service: SettingsService = Depends(get_settings_service),
):
    """New weights apply to every complaint scored from now on. With
    recalculate_open, open complaints are re-scored too."""
    view, rescored = service.set_priority_weights(
        payload.weights.model_dump(), user, payload.recalculate_open)
    return {**view, "rescored": rescored}


@router.delete("/priority-weights", response_model=PriorityWeightsOut)
def reset_priority_weights(
    user: ManagerUser,
    recalculate_open: bool = Query(False),
    service: SettingsService = Depends(get_settings_service),
):
    """Go back to the defaults from .env."""
    view, rescored = service.reset_priority_weights(user, recalculate_open)
    return {**view, "rescored": rescored}
