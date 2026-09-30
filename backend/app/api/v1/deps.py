"""FastAPI dependencies: services per request, and the authentication guard.

Route handlers never touch the User model directly. They declare
`user: CurrentUser` (any signed-in user) or add `require_role(...)`.
"""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorisedError
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import AuthService, UserService
from app.services.complaint_service import ComplaintService
from app.services.generated_content_service import GeneratedContentService
from app.services.prediction_service import PredictionService

# tokenUrl points at the form-based endpoint so the "Authorize" button in
# /docs works. auto_error=False lets us return our own JSON error shape.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_complaint_service(db: Session = Depends(get_db)) -> Iterator[ComplaintService]:
    yield ComplaintService(db)


def get_prediction_service(
    db: Session = Depends(get_db),
) -> Iterator[PredictionService]:
    yield PredictionService(db)


def get_generated_content_service(
    db: Session = Depends(get_db),
) -> Iterator[GeneratedContentService]:
    yield GeneratedContentService(db)


def get_auth_service(db: Session = Depends(get_db)) -> Iterator[AuthService]:
    yield AuthService(db)


def get_user_service(db: Session = Depends(get_db)) -> Iterator[UserService]:
    yield UserService(db)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    """FR-37, FR-40. Rejects missing, invalid and expired tokens with 401."""
    if not token:
        raise UnauthorisedError("Not signed in")
    payload = decode_access_token(token)
    return auth.user_from_token_subject(payload["sub"])


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[..., User]:
    """FR-38. Use as a dependency: Depends(require_role(UserRole.MANAGER, ...)).

    A signed-in user without one of the roles gets 403; no token gets 401.
    """
    allowed = frozenset(roles)

    def guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                "This action needs the role: " + " or ".join(sorted(r.value for r in allowed))
            )
        return user

    return guard


# Role groups used across the routers. Administrators can do everything.
STAFF = (UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN)
MANAGERS = (UserRole.MANAGER, UserRole.ADMIN)
ADMINS = (UserRole.ADMIN,)

StaffUser = Annotated[User, Depends(require_role(*STAFF))]
ManagerUser = Annotated[User, Depends(require_role(*MANAGERS))]
AdminUser = Annotated[User, Depends(require_role(*ADMINS))]
