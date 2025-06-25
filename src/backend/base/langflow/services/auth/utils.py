import base64
import random
import warnings
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, WebSocketException, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from jose import JWTError, jwt
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocket

from langflow.services.database.models.api_key.crud import check_key
from langflow.services.database.models.user.crud import get_user_by_id, get_user_by_username, update_user_last_login_at
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service, get_session, get_settings_service
from langflow.services.settings.service import SettingsService
from langflow.services.auth.clerk_utils import verify_clerk_token, get_clerk_user_id, get_clerk_username, get_clerk_user_email

if TYPE_CHECKING:
    from langflow.services.database.models.api_key.model import ApiKey

oauth2_login = OAuth2PasswordBearer(tokenUrl="api/v1/login", auto_error=False)

API_KEY_NAME = "x-api-key"

api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)

MINIMUM_KEY_LENGTH = 32


# Source: https://github.com/mrtolkien/fastapi_simple_security/blob/master/fastapi_simple_security/security_api_key.py
async def api_key_security(
    query_param: Annotated[str, Security(api_key_query)],
    header_param: Annotated[str, Security(api_key_header)],
) -> UserRead | None:
    settings_service = get_settings_service()
    result: ApiKey | User | None

    async with get_db_service().with_session() as db:
        if settings_service.auth_settings.AUTO_LOGIN:
            # Get the first user
            if not settings_service.auth_settings.SUPERUSER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing first superuser credentials",
                )
            warnings.warn(
                (
                    "In v1.5, the default behavior of AUTO_LOGIN authentication will change to require a valid API key"
                    " or JWT. If you integrated with Langflow prior to v1.5, make sure to update your code to pass an "
                    "API key or JWT when authenticating with protected endpoints."
                ),
                DeprecationWarning,
                stacklevel=2,
            )
            if query_param or header_param:
                result = await check_key(db, query_param or header_param)
            else:
                result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        elif query_param:
            result = await check_key(db, query_param)

        else:
            result = await check_key(db, header_param)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )
        if isinstance(result, User):
            return UserRead.model_validate(result, from_attributes=True)
    msg = "Invalid result type"
    raise ValueError(msg)


async def ws_api_key_security(
    api_key: str | None,
) -> UserRead:
    settings = get_settings_service()
    async with get_db_service().with_session() as db:
        if settings.auth_settings.AUTO_LOGIN:
            if not settings.auth_settings.SUPERUSER:
                # internal server misconfiguration
                raise WebSocketException(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Missing first superuser credentials",
                )
            warnings.warn(
                ("In v1.5, AUTO_LOGIN will *require* a valid API key or JWT. Please update your clients accordingly."),
                DeprecationWarning,
                stacklevel=2,
            )
            if api_key:
                result = await check_key(db, api_key)
            else:
                result = await get_user_by_username(db, settings.auth_settings.SUPERUSER)

        # normal path: must provide an API key
        else:
            if not api_key:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="An API key must be passed as query or header",
                )
            result = await check_key(db, api_key)

        # key was invalid or missing
        if not result:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or missing API key",
            )

        # convert SQL-model User → pydantic UserRead
        if isinstance(result, User):
            return UserRead.model_validate(result, from_attributes=True)

    # fallback: something unexpected happened
    raise WebSocketException(
        code=status.WS_1011_INTERNAL_ERROR,
        reason="Authentication subsystem error",
    )


async def get_current_user(
    token: Annotated[str, Security(oauth2_login)],
    query_param: Annotated[str, Security(api_key_query)],
    header_param: Annotated[str, Security(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if token:
        return await get_current_user_by_jwt(token, db)
    user = await api_key_security(query_param, header_param)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing API key",
    )


async def get_current_user_by_jwt(
    token: str,
    db: AsyncSession,
) -> User:
    settings_service = get_settings_service()

    if isinstance(token, Coroutine):
        token = await token

    if settings_service.auth_settings.CLERK_AUTH_ENABLED:
        try:
            claims = verify_clerk_token(token)
            clerk_user_id = get_clerk_user_id(claims)
            email = get_clerk_user_email(claims)
            username = get_clerk_username(claims)  # optional, you could use clerk_user_id too

            user = await get_user_by_username(db, clerk_user_id)
            if not user:
                # ✅ Auto-provision new user from Clerk
                user = User(
                    username=clerk_user_id,
                    is_active=True,
                    is_superuser=False,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

            if not user.is_active:
                raise HTTPException(status_code=401, detail="User is inactive")

            return user
        except Exception as e:
            logger.exception("Clerk JWT validation failed")
            raise HTTPException(status_code=401, detail="Invalid Clerk token") from e
    else:
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
            user_id: UUID = payload.get("sub")  # type: ignore[assignment]
            token_type: str = payload.get("type")  # type: ignore[assignment]
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
            logger.debug("JWT validation failed: Invalid token format or signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        user = await get_user_by_id(db, user_id)
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
    db: AsyncSession,
) -> User | UserRead:
    token = websocket.cookies.get("access_token_lf") or websocket.query_params.get("token")
    if token:
        user = await get_current_user_by_jwt(token, db)
        if user:
            return user

    api_key = (
        websocket.query_params.get("x-api-key")
        or websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key")
        or websocket.headers.get("api_key")
    )
    if api_key:
        user_read = await ws_api_key_security(api_key)
        if user_read:
            return user_read

    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION, reason="Missing or invalid credentials (cookie, token or API key)."
    )


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user


async def get_current_active_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
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


async def create_super_user(
    username: str,
    password: str,
    db: AsyncSession,
) -> User:
    super_user = await get_user_by_username(db, username)

    if not super_user:
        super_user = User(
            username=username,
            password=get_password_hash(password),
            is_superuser=True,
            is_active=True,
            last_login_at=None,
        )

        db.add(super_user)
        await db.commit()
        await db.refresh(super_user)

    return super_user


async def create_user_longterm_token(db: AsyncSession) -> tuple[UUID, dict]:
    settings_service = get_settings_service()

    username = settings_service.auth_settings.SUPERUSER
    super_user = await get_user_by_username(db, username)
    if not super_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super user hasn't been created")
    access_token_expires_longterm = timedelta(days=365)
    access_token = create_token(
        data={"sub": str(super_user.id), "type": "access"},
        expires_delta=access_token_expires_longterm,
    )

    # Update: last_login_at
    await update_user_last_login_at(super_user.id, db)

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


async def create_user_tokens(user_id: UUID, db: AsyncSession, *, update_last_login: bool = False) -> dict:
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
        await update_user_last_login_at(user_id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def create_refresh_token(refresh_token: str, db: AsyncSession):
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
        user_id: UUID = payload.get("sub")  # type: ignore[assignment]
        token_type: str = payload.get("type")  # type: ignore[assignment]

        if user_id is None or token_type == "":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_exists = await get_user_by_id(db, user_id)

        if user_exists is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        return await create_user_tokens(user_id, db)

    except JWTError as e:
        logger.exception("JWT decoding error")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


async def authenticate_user(username: str, password: str, db: AsyncSession) -> User | None:
    user = await get_user_by_username(db, username)

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
    if len(s) < MINIMUM_KEY_LENGTH:
        # Use the input as a seed for the random number generator
        random.seed(s)
        # Generate 32 random bytes
        key = bytes(random.getrandbits(8) for _ in range(32))
        key = base64.urlsafe_b64encode(key)
    else:
        key = add_padding(s).encode()
    return key


def get_fernet(settings_service: SettingsService):
    secret_key: str = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    valid_key = ensure_valid_key(secret_key)
    return Fernet(valid_key)


def encrypt_api_key(api_key: str, settings_service: SettingsService):
    fernet = get_fernet(settings_service)
    # Two-way encryption
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key.decode()


def decrypt_api_key(encrypted_api_key: str, settings_service: SettingsService):
    """Decrypt the provided encrypted API key using Fernet decryption.

    This function first attempts to decrypt the API key by encoding it,
    assuming it is a properly encoded string. If that fails, it logs a detailed
    debug message including the exception information and retries decryption
    using the original string input.

    Args:
        encrypted_api_key (str): The encrypted API key.
        settings_service (SettingsService): Service providing authentication settings.

    Returns:
        str: The decrypted API key, or an empty string if decryption cannot be performed.
    """
    fernet = get_fernet(settings_service)
    if isinstance(encrypted_api_key, str):
        try:
            return fernet.decrypt(encrypted_api_key.encode()).decode()
        except Exception as primary_exception:  # noqa: BLE001
            logger.debug(
                "Decryption using UTF-8 encoded API key failed. Error: %s. "
                "Retrying decryption using the raw string input.",
                primary_exception,
            )
            return fernet.decrypt(encrypted_api_key).decode()
    return ""

async def get_current_user_flexible(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Depends(oauth2_login)],
    query_key: Annotated[str | None, Security(api_key_query)] = None,
    header_key: Annotated[str | None, Security(api_key_header)] = None,
) -> User:
    settings = get_settings_service()

    if token and not token.startswith("Bearer "):
        token = token.strip()

    if settings.auth_settings.CLERK_AUTH_ENABLED:
        # Prefer Authorization header; if not available, fallback to Clerk cookies
        if not token:
            token = request.cookies.get("__session") or request.cookies.get("access_token_lf")

        if token:
            try:
                return await get_current_user_by_jwt(token, db)
            except HTTPException as e:
                # Allow fallback to legacy if Clerk token is invalid
                pass

    # Fallback: legacy API key auth or legacy bearer token
    key = query_key or header_key or token  # token might be legacy JWT

    if not key:
        raise HTTPException(status_code=401, detail="API key or token required")

    try:
        return await get_current_user_by_jwt(key, db)
    except Exception:
        # If legacy token fails, try API key flow
        user = await check_key(db, key)
        if not user:
            raise HTTPException(status_code=403, detail="Invalid API key")
        return user
