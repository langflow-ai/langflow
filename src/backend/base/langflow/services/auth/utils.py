import base64
import random
import warnings
from datetime import datetime, timedelta, timezone
from typing import Annotated, Coroutine, Optional, Union
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from jose import JWTError, jwt
from loguru import logger
from sqlmodel import Session
from starlette.websockets import WebSocket

from langflow.services.database.models.api_key.crud import check_key
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.crud import get_user_by_id, get_user_by_username, update_user_last_login_at
from langflow.services.database.models.user.model import User, UserRead
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
) -> Optional[UserRead]:
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
        return UserRead.model_validate(result.user, from_attributes=True)
    elif isinstance(result, User):
        return UserRead.model_validate(result, from_attributes=True)
    raise ValueError("Invalid result type")


async def get_current_user(
    token: str = Security(oauth2_login),
    query_param: str = Security(api_key_query),
    header_param: str = Security(api_key_header),
    db: Session = Depends(get_session),
) -> User:
    if token:
        return await get_current_user_by_jwt(token, db)
    else:
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

    if isinstance(token, Coroutine):
        token = await token

    secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    if secret_key is None:
        logger.error("Secret key is not set in settings.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            # Careful not to leak sensitive information
            detail="Authentication failure: Verify authentication settings.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            payload = jwt.decode(token, secret_key, algorithms=[settings_service.auth_settings.ALGORITHM])
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore
        if expires := payload.get("exp", None):
            expires_datetime = datetime.fromtimestamp(expires, timezone.utc)
            if datetime.now(timezone.utc) > expires_datetime:
                logger.info("Token expired for user")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        if user_id is None or token_type is None:
            logger.info(f"Invalid token payload. Token type: {token_type}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token details.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        logger.error(f"JWT decoding error: {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        logger.info("User not found or inactive.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user


def get_current_active_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges")
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
    super_user = get_user_by_username(db, username)
    if not super_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super user hasn't been created")
    access_token_expires_longterm = timedelta(days=365)
    access_token = create_token(
        data={"sub": str(super_user.id), "type": "access"},
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
        data={"sub": str(user_id), "type": "api_key"},
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
        data={"sub": str(user_id), "type": "access"},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(seconds=settings_service.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS)
    refresh_token = create_token(
        data={"sub": str(user_id), "type": "refresh"},
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
        # Ignore warning about datetime.utcnow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            payload = jwt.decode(
                refresh_token,
                settings_service.auth_settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings_service.auth_settings.ALGORITHM],
            )
        user_id: UUID = payload.get("sub")  # type: ignore
        token_type: str = payload.get("type")  # type: ignore

        if user_id is None or token_type == "":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_exists = get_user_by_id(db, user_id)

        if user_exists is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        return create_user_tokens(user_id, db)

    except JWTError as e:
        logger.error(f"JWT decoding error: {e}")
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Waiting for approval")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    return user if verify_password(password, user.password) else None


def add_padding(s):
    # Calculate the number of padding characters needed
    padding_needed = 4 - len(s) % 4
    return s + "=" * padding_needed


def ensure_valid_key(s: str) -> bytes:
    # If the key is too short, we'll use it as a seed to generate a valid key
    if len(s) < 32:
        # Use the input as a seed for the random number generator
        random.seed(s)
        # Generate 32 random bytes
        key = bytes(random.getrandbits(8) for _ in range(32))
        key = base64.urlsafe_b64encode(key)
    else:
        key = add_padding(s).encode()
    return key


def get_fernet(settings_service=Depends(get_settings_service)):
    SECRET_KEY: str = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    valid_key = ensure_valid_key(SECRET_KEY)
    fernet = Fernet(valid_key)
    return fernet


def encrypt_api_key(api_key: str, settings_service=Depends(get_settings_service)):
    fernet = get_fernet(settings_service)
    # Two-way encryption
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key.decode()


def decrypt_api_key(encrypted_api_key: str, settings_service=Depends(get_settings_service)):
    fernet = get_fernet(settings_service)
    decrypted_key = ""
    # Two-way decryption
    if isinstance(encrypted_api_key, str):
        try:
            decrypted_key = fernet.decrypt(encrypted_api_key.encode()).decode()
        except Exception:
            decrypted_key = fernet.decrypt(encrypted_api_key).decode()
    return decrypted_key
