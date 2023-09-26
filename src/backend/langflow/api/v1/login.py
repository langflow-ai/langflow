from sqlmodel import Session
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from langflow.services.getters import get_session
from langflow.api.v1.schemas import Token
from langflow.services.auth.utils import (
    authenticate_user,
    create_user_tokens,
    create_refresh_token,
    create_user_longterm_token,
    get_current_active_user,
)

from langflow.services.getters import get_settings_service

router = APIRouter(tags=["Login"])


@router.post("/login", response_model=Token)
async def login_to_get_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session),
    # _: Session = Depends(get_current_active_user)
):
    try:
        user = authenticate_user(form_data.username, form_data.password, db)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if user:
        return create_user_tokens(user_id=user.id, db=db, update_last_login=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/auto_login")
async def auto_login(
    db: Session = Depends(get_session), settings_service=Depends(get_settings_service)
):
    if settings_service.auth_settings.AUTO_LOGIN:
        return create_user_longterm_token(db)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Auto login is disabled. Please enable it in the settings",
            "auto_login": False,
        },
    )


@router.post("/refresh")
async def refresh_token(
    token: str, current_user: Session = Depends(get_current_active_user)
):
    if token:
        return create_refresh_token(token)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
