from datetime import datetime, timedelta, timezone
from typing import Annotated, Coroutine, Optional, Union
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session
from starlette.websockets import WebSocket

from langflow.services.database.models.api_key.crud import check_key
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.crud import (
    get_user_by_id,
    get_user_by_username,
    update_user_last_login_at,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session, get_settings_service

oauth2_login = OAuth2PasswordBearer(tokenUrl="api/v1/login", auto_error=False)

API_KEY_NAME = "x-api-key"

api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)


# Source: https://github.com/mrtolkien/fastapi_simple_security/blob/master/fastapi_simple_security/security_api_key.py
async def api_key_security(
    query_param: str = Security(api_key_query),
    header_param: str = Security(api_key_header),
    db: Session = Depends(get_session),
) -> Optional[User]:
    settings_service = get_settings_service()
    result: Optional[Union[ApiKey, User]] = None
    if settings_service.auth_settings.AUTO_LOGIN:
        # Get the first user
        if not settings_service.auth_settings.SUPERUSER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing first superuser credentials",
            )

        result = get_user_by_username(db, settings_service.auth_settings.SUPERUSER)

    elif not query_param and not header_param:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An API key must be passed as query or header",
        )

    elif query_param:
        result = check_key(db, query_param)

    else:
        result = check_key(db, header_param)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    if isinstance(result, ApiKey):
        return result.user
    elif isinstance(result, User):
        return result


async def get_current_user(
    token: str = Security(oauth2_login),
    query_param: str = Security(api_key_query),
    header_param: str = Security(api_key_header),
    db: Session = Depends(get_session),
) -> User:
    if token:
        return await get_current_user_by_jwt(token, db)
    else:
        if not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key as query or header, or a JWT token must be passed",
            )
        user = await api_key_security(query_param, header_param, db)
        if user:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )


async def get_current_user_by_jwt(
    token: Annotated[str, Depends(oauth2_login)],
    db: Session = Depends(get_session),
) -> User:
    settings_service = get_settings_service()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if isinstance(token, Coroutine):
        token = await token

    if settings_service.auth_settings.SECRET_KEY.get_secret_value() is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            settings_service.auth_settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings_service.auth_settings.ALGORITHM],
        )
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore
        if expires := payload.get("exp", None):
            expires_datetime = datetime.fromtimestamp(expires, timezone.utc)
            # TypeError: can't compare offset-naive and offset-aware datetimes
            if datetime.now(timezone.utc) > expires_datetime:
                raise credentials_exception

        if user_id is None or token_type:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception from e

    user = get_user_by_id(db, user_id)  # type: ignore
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_user_for_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_session),
    query_param: str = Security(api_key_query),
) -> Optional[User]:
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("x-api-key")
    if token:
        return await get_current_user_by_jwt(token, db)
    elif api_key:
        return await api_key_security(api_key, query_param, db)
    else:
        return None


def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    if not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


def verify_password(plain_password, hashed_password):
    settings_service = get_settings_service()
    return settings_service.auth_settings.pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    settings_service = get_settings_service()
    return settings_service.auth_settings.pwd_context.hash(password)


def create_token(data: dict, expires_delta: timedelta):
    settings_service = get_settings_service()

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode["exp"] = expire

    return jwt.encode(
        to_encode,
        settings_service.auth_settings.SECRET_KEY.get_secret_value(),
        algorithm=settings_service.auth_settings.ALGORITHM,
    )


def create_super_user(
    username: str,
    password: str,
    db: Session = Depends(get_session),
) -> User:
    super_user = get_user_by_username(db, username)

    if not super_user:
        super_user = User(
            username=username,
            password=get_password_hash(password),
            is_superuser=True,
            is_active=True,
            last_login_at=None,
        )

        db.add(super_user)
        db.commit()
        db.refresh(super_user)

    return super_user


def create_user_longterm_token(db: Session = Depends(get_session)) -> tuple[UUID, dict]:
    settings_service = get_settings_service()
    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing first superuser credentials",
        )
    super_user = create_super_user(db=db, username=username, password=password)

    access_token_expires_longterm = timedelta(days=365)
    access_token = create_token(
        data={"sub": str(super_user.id)},
        expires_delta=access_token_expires_longterm,
    )

    # Update: last_login_at
    update_user_last_login_at(super_user.id, db)

    return super_user.id, {
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


def create_user_tokens(user_id: UUID, db: Session = Depends(get_session), update_last_login: bool = False) -> dict:
    settings_service = get_settings_service()

    access_token_expires = timedelta(seconds=settings_service.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = create_token(
        data={"sub": str(user_id)},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(seconds=settings_service.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS)
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
    settings_service = get_settings_service()

    try:
        payload = jwt.decode(
            refresh_token,
            settings_service.auth_settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings_service.auth_settings.ALGORITHM],
        )
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore

        if user_id is None or token_type is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        return create_user_tokens(user_id, db)

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


def authenticate_user(username: str, password: str, db: Session = Depends(get_session)) -> Optional[User]:
    user = get_user_by_username(db, username)

    if not user:
        return None

    if not user.is_active:
        if not user.last_login_at:
            raise HTTPException(status_code=400, detail="Waiting for approval")
        raise HTTPException(status_code=400, detail="Inactive user")

    return user if verify_password(password, user.password) else None


def add_padding(s):
    # Calculate the number of padding characters needed
    padding_needed = 4 - len(s) % 4
    return s + "=" * padding_needed


def get_fernet(settings_service=Depends(get_settings_service)):
    SECRET_KEY = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    # It's important that your secret key is 32 url-safe base64-encoded byte
    padded_secret_key = add_padding(SECRET_KEY)
    fernet = Fernet(padded_secret_key)
    return fernet


def encrypt_api_key(api_key: str, settings_service=Depends(get_settings_service)):
    fernet = get_fernet(settings_service)
    # Two-way encryption
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key.decode()


def decrypt_api_key(encrypted_api_key: str, settings_service=Depends(get_settings_service)):
    fernet = get_fernet(settings_service)
    # Two-way decryption
    if isinstance(encrypted_api_key, str):
        encoded_bytes = encrypted_api_key.encode()
    else:
        encoded_bytes = encrypted_api_key
    decrypted_key = fernet.decrypt(encoded_bytes).decode()
    return decrypted_key
