from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.deps import CurrentUser, get_auth_service
from app.schemas.auth import LoginRequest, TokenOut, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(auth: AuthService, username: str, password: str) -> TokenOut:
    token, user = auth.login(username, password)
    return TokenOut(
        access_token=token,
        expires_in=auth.token_lifetime_seconds(),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
def login(
    payload: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """FR-37. JSON login used by the dashboard."""
    return _token_response(auth, payload.username, payload.password)


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthService = Depends(get_auth_service),
):
    """Form-encoded login, used only by the Authorize button in /docs."""
    return _token_response(auth, form.username, form.password)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    """The signed-in user. The dashboard calls this to restore a session."""
    return user
