import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.deps import AdminUser, get_user_service
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services.auth_service import UserService

# FR-39: user management is restricted to administrators.
router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    admin: AdminUser,
    service: UserService = Depends(get_user_service),
):
    return service.list()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    admin: AdminUser,
    service: UserService = Depends(get_user_service),
):
    return service.create(payload, actor=admin)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: AdminUser,
    service: UserService = Depends(get_user_service),
):
    """Change role, activate/deactivate, or reset the password."""
    return service.update(user_id, payload, actor=admin)
