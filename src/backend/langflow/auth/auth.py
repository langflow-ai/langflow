from uuid import UUID
from typing import Annotated
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from datetime import datetime, timedelta, timezone

from langflow.services.utils import get_settings_manager, get_session

from langflow.database.models.user import (
    User,
    get_user_by_id,
    get_user_by_username,
    update_user_last_login_at,
)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_session)
) -> User:
    settings_manager = get_settings_manager()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings_manager.settings.SECRET_KEY,
            algorithms=[settings_manager.settings.ALGORITHM],
        )
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore

        if user_id is None or token_type:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception from e

    user = get_user_by_id(db, user_id)  # type: ignore
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_token(data: dict, expires_delta: timedelta):
    settings_manager = get_settings_manager()

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode["exp"] = expire

    return jwt.encode(
        to_encode,
        settings_manager.settings.SECRET_KEY,
        algorithm=settings_manager.settings.ALGORITHM,
    )


def create_super_user(db: Session = Depends(get_session)) -> User:
    settings_manager = get_settings_manager()

    super_user = get_user_by_username(db, settings_manager.settings.FIRST_SUPERUSER)

    if not super_user:
        super_user = User(
            username=settings_manager.settings.FIRST_SUPERUSER,
            password=get_password_hash(
                settings_manager.settings.FIRST_SUPERUSER_PASSWORD
            ),
            is_superuser=True,
            is_active=True,
            last_login_at=None,
        )

        db.add(super_user)
        db.commit()
        db.refresh(super_user)

    return super_user


def create_user_longterm_token(db: Session = Depends(get_session)) -> dict:
    super_user = create_super_user(db)

    access_token_expires_longterm = timedelta(days=365)
    access_token = create_token(
        data={"sub": str(super_user.id)},
        expires_delta=access_token_expires_longterm,
    )

    # Update: last_login_at
    update_user_last_login_at(super_user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": None,
        "token_type": "bearer",
    }


def create_user_api_key(user_id: UUID) -> dict:
    access_token = create_token(
        data={"sub": str(user_id), "role": "api_key"},
        expires_delta=timedelta(days=365 * 2),
    )

    return {"api_key": access_token}


def get_user_id_from_token(token: str) -> UUID:
    try:
        user_id = jwt.get_unverified_claims(token)["sub"]
        return UUID(user_id)
    except (KeyError, JWTError, ValueError):
        return UUID(int=0)


def create_user_tokens(
    user_id: UUID, db: Session = Depends(get_session), update_last_login: bool = False
) -> dict:
    settings_manager = get_settings_manager()

    access_token_expires = timedelta(
        minutes=settings_manager.settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_token(
        data={"sub": str(user_id)},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(
        minutes=settings_manager.settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    refresh_token = create_token(
        data={"sub": str(user_id), "type": "rf"},
        expires_delta=refresh_token_expires,
    )

    # Update: last_login_at
    if update_last_login:
        update_user_last_login_at(user_id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def create_refresh_token(refresh_token: str, db: Session = Depends(get_session)):
    settings_manager = get_settings_manager()

    try:
        payload = jwt.decode(
            refresh_token,
            settings_manager.settings.SECRET_KEY,
            algorithms=[settings_manager.settings.ALGORITHM],
        )
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore

        if user_id is None or token_type is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        return create_user_tokens(user_id, db)

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


def authenticate_user(
    username: str, password: str, db: Session = Depends(get_session)
) -> User | None:
    user = get_user_by_username(db, username)

    if not user:
        return None

    if not user.is_active:
        if not user.last_login_at:
            raise HTTPException(status_code=400, detail="Waiting for approval")
        raise HTTPException(status_code=400, detail="Inactive user")

    return user if verify_password(password, user.password) else None
