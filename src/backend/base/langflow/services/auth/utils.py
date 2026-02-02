import base64
import random
import warnings
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Final
from uuid import UUID

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, WebSocketException, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jwt import InvalidTokenError
from lfx.log.logger import logger
from lfx.services.deps import injectable_session_scope, session_scope
from lfx.services.settings.service import SettingsService
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocket

from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.services.database.models.api_key.crud import check_key
from langflow.services.database.models.user.crud import get_user_by_id, get_user_by_username, update_user_last_login_at
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from langflow.services.database.models.api_key.model import ApiKey


class OAuth2PasswordBearerCookie(OAuth2PasswordBearer):
    """Custom OAuth2 scheme that checks Authorization header first, then cookies.

    This allows the application to work with HttpOnly cookies while supporting
    explicit Authorization headers for backward compatibility and testing scenarios.
    If an explicit Authorization header is provided, it takes precedence over cookies.
    """

    async def __call__(self, request: Request) -> str | None:
        # First, check for explicit Authorization header (for backward compatibility and testing)
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer" and param:
            return param

        # Fall back to cookie (for HttpOnly cookie support in browser-based clients)
        token = request.cookies.get("access_token_lf")
        if token:
            return token

        # If auto_error is True, this would raise an exception
        # Since we set auto_error=False, return None
        return None


oauth2_login = OAuth2PasswordBearerCookie(tokenUrl="api/v1/login", auto_error=False)

API_KEY_NAME = "x-api-key"

api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)

MINIMUM_KEY_LENGTH = 32
AUTO_LOGIN_WARNING = "In v2.0, LANGFLOW_SKIP_AUTH_AUTO_LOGIN will be removed. Please update your authentication method."
AUTO_LOGIN_ERROR = (
    "Since v1.5, LANGFLOW_AUTO_LOGIN requires a valid API key. "
    "Set LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true to skip this check. "
    "Please update your authentication method."
)

REFRESH_TOKEN_TYPE: Final[str] = "refresh"  # noqa: S105
ACCESS_TOKEN_TYPE: Final[str] = "access"  # noqa: S105

# JWT key configuration error messages
PUBLIC_KEY_NOT_CONFIGURED_ERROR: Final[str] = (
    "Server configuration error: Public key not configured for asymmetric JWT algorithm."
)
SECRET_KEY_NOT_CONFIGURED_ERROR: Final[str] = "Server configuration error: Secret key not configured."  # noqa: S105


class JWTKeyError(HTTPException):
    """Raised when JWT key configuration is invalid."""

    def __init__(self, detail: str, *, include_www_authenticate: bool = True):
        headers = {"WWW-Authenticate": "Bearer"} if include_www_authenticate else None
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        )


def get_jwt_verification_key(settings_service: SettingsService) -> str:
    """Get the appropriate key for JWT verification based on configured algorithm.

    For asymmetric algorithms (RS256, RS512): returns public key
    For symmetric algorithms (HS256): returns secret key
    """
    algorithm = settings_service.auth_settings.ALGORITHM

    if algorithm.is_asymmetric():
        verification_key = settings_service.auth_settings.PUBLIC_KEY
        if not verification_key:
            logger.error("Public key is not set in settings for RS256/RS512.")
            raise JWTKeyError(PUBLIC_KEY_NOT_CONFIGURED_ERROR)
        return verification_key

    secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    if secret_key is None:
        logger.error("Secret key is not set in settings.")
        raise JWTKeyError(SECRET_KEY_NOT_CONFIGURED_ERROR)
    return secret_key


def get_jwt_signing_key(settings_service: SettingsService) -> str:
    """Get the appropriate key for JWT signing based on configured algorithm.

    For asymmetric algorithms (RS256, RS512): returns private key
    For symmetric algorithms (HS256): returns secret key
    """
    algorithm = settings_service.auth_settings.ALGORITHM

    if algorithm.is_asymmetric():
        return settings_service.auth_settings.PRIVATE_KEY.get_secret_value()

    return settings_service.auth_settings.SECRET_KEY.get_secret_value()


# Source: https://github.com/mrtolkien/fastapi_simple_security/blob/master/fastapi_simple_security/security_api_key.py
async def api_key_security(
    query_param: Annotated[str, Security(api_key_query)],
    header_param: Annotated[str, Security(api_key_header)],
) -> UserRead | None:
    settings_service = get_settings_service()
    result: ApiKey | User | None

    async with session_scope() as db:
        if settings_service.auth_settings.AUTO_LOGIN:
            # Get the first user
            if not settings_service.auth_settings.SUPERUSER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing first superuser credentials",
                )
            if not query_param and not header_param:
                if settings_service.auth_settings.skip_auth_auto_login:
                    result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
                    logger.warning(AUTO_LOGIN_WARNING)
                    return UserRead.model_validate(result, from_attributes=True)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=AUTO_LOGIN_ERROR,
                )
            result = await check_key(db, query_param or header_param)

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        else:
            result = await check_key(db, query_param or header_param)

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
    async with session_scope() as db:
        if settings.auth_settings.AUTO_LOGIN:
            if not settings.auth_settings.SUPERUSER:
                # internal server misconfiguration
                raise WebSocketException(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Missing first superuser credentials",
                )
            if not api_key:
                if settings.auth_settings.skip_auth_auto_login:
                    result = await get_user_by_username(db, settings.auth_settings.SUPERUSER)
                    logger.warning(AUTO_LOGIN_WARNING)
                else:
                    raise WebSocketException(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason=AUTO_LOGIN_ERROR,
                    )
            else:
                result = await check_key(db, api_key)

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
    db: Annotated[AsyncSession, Depends(injectable_session_scope)],
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

    algorithm = settings_service.auth_settings.ALGORITHM
    verification_key = get_jwt_verification_key(settings_service)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            payload = jwt.decode(token, verification_key, algorithms=[algorithm])
        user_id: UUID = payload.get("sub")  # type: ignore[assignment]
        token_type: str = payload.get("type")  # type: ignore[assignment]

        if token_type != ACCESS_TOKEN_TYPE:
            logger.error(f"Token type is invalid: {token_type}. Expected: {ACCESS_TOKEN_TYPE}.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid.",
                headers={"WWW-Authenticate": "Bearer"},
            )
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
    except InvalidTokenError as e:
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


async def get_current_user_for_sse(request: Request) -> User | UserRead:
    """Authenticate user for SSE endpoints.

    Similar to websocket authentication, accepts either:
    - Cookie authentication (access_token_lf)
    - API key authentication (x-api-key query param)

    Args:
        request: The FastAPI request object

    Returns:
        User or UserRead: The authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    # Try cookie authentication first
    token = request.cookies.get("access_token_lf")
    if token:
        try:
            async with session_scope() as db:
                user = await get_current_user_by_jwt(token, db)
                if user:
                    return user
        except HTTPException:
            pass

    # Try API key authentication
    api_key = request.query_params.get("x-api-key") or request.headers.get("x-api-key")
    if api_key:
        user_read = await ws_api_key_security(api_key)
        if user_read:
            return user_read

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Missing or invalid credentials (cookie or API key).",
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


async def get_webhook_user(flow_id: str, request: Request) -> UserRead:
    """Get the user for webhook execution.

    When WEBHOOK_AUTH_ENABLE=false, allows execution as the flow owner without API key.
    When WEBHOOK_AUTH_ENABLE=true, requires API key authentication and validates flow ownership.

    Args:
        flow_id: The ID of the flow being executed
        request: The FastAPI request object

    Returns:
        UserRead: The user to execute the webhook as

    Raises:
        HTTPException: If authentication fails or user doesn't have permission
    """
    settings_service = get_settings_service()

    if not settings_service.auth_settings.WEBHOOK_AUTH_ENABLE:
        # When webhook auth is disabled, run webhook as the flow owner without requiring API key
        try:
            flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
            if flow_owner is None:
                raise HTTPException(status_code=404, detail="Flow not found")
            return flow_owner  # noqa: TRY300
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Flow not found") from exc

    # When webhook auth is enabled, require API key authentication
    api_key_header_val = request.headers.get("x-api-key")
    api_key_query_val = request.query_params.get("x-api-key")

    # Check if API key is provided
    if not api_key_header_val and not api_key_query_val:
        raise HTTPException(status_code=403, detail="API key required when webhook authentication is enabled")

    # Use the provided API key (prefer header over query param)
    api_key = api_key_header_val or api_key_query_val

    try:
        # Validate API key directly without AUTO_LOGIN fallback
        async with session_scope() as db:
            result = await check_key(db, api_key)
            if not result:
                logger.warning("Invalid API key provided for webhook")
                raise HTTPException(status_code=403, detail="Invalid API key")

            authenticated_user = UserRead.model_validate(result, from_attributes=True)
            logger.info("Webhook API key validated successfully")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as exc:
        # Handle other exceptions
        logger.error(f"Webhook API key validation error: {exc}")
        raise HTTPException(status_code=403, detail="API key authentication failed") from exc

    # Get flow owner to check if authenticated user owns this flow
    try:
        flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
        if flow_owner is None:
            raise HTTPException(status_code=404, detail="Flow not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Flow not found") from exc

    if flow_owner.id != authenticated_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You can only execute webhooks for flows you own")

    return authenticated_user


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

    algorithm = settings_service.auth_settings.ALGORITHM
    signing_key = get_jwt_signing_key(settings_service)

    return jwt.encode(
        to_encode,
        signing_key,
        algorithm=algorithm,
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
        try:
            await db.commit()
            await db.refresh(super_user)
        except IntegrityError:
            # Race condition - another worker created the user
            await db.rollback()
            super_user = await get_user_by_username(db, username)
            if not super_user:
                raise  # Re-raise if it's not a race condition
        except Exception:  # noqa: BLE001
            logger.debug("Error creating superuser.", exc_info=True)

    return super_user


async def create_user_longterm_token(db: AsyncSession) -> tuple[UUID, dict]:
    settings_service = get_settings_service()
    if not settings_service.auth_settings.AUTO_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Auto login required to create a long-term token"
        )

    # Prefer configured username; fall back to default or any existing superuser
    # NOTE: This user name cannot be a dynamic current user name since it is only used when autologin is True
    username = settings_service.auth_settings.SUPERUSER
    super_user = await get_user_by_username(db, username)
    if not super_user:
        from langflow.services.database.models.user.crud import get_all_superusers

        superusers = await get_all_superusers(db)
        super_user = superusers[0] if superusers else None

    if not super_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super user hasn't been created")
    access_token_expires_longterm = timedelta(days=365)
    access_token = create_token(
        data={"sub": str(super_user.id), "type": ACCESS_TOKEN_TYPE},
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
        claims = jwt.decode(token, options={"verify_signature": False})
        user_id = claims["sub"]
        return UUID(user_id)
    except (KeyError, InvalidTokenError, ValueError):
        return UUID(int=0)


async def create_user_tokens(user_id: UUID, db: AsyncSession, *, update_last_login: bool = False) -> dict:
    settings_service = get_settings_service()

    access_token_expires = timedelta(seconds=settings_service.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = create_token(
        data={"sub": str(user_id), "type": ACCESS_TOKEN_TYPE},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(seconds=settings_service.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS)
    refresh_token = create_token(
        data={"sub": str(user_id), "type": REFRESH_TOKEN_TYPE},
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

    algorithm = settings_service.auth_settings.ALGORITHM
    verification_key = get_jwt_verification_key(settings_service)

    try:
        # Ignore warning about datetime.utcnow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            payload = jwt.decode(
                refresh_token,
                verification_key,
                algorithms=[algorithm],
            )
        user_id: UUID = payload.get("sub")  # type: ignore[assignment]
        token_type: str = payload.get("type")  # type: ignore[assignment]

        if user_id is None or token_type != REFRESH_TOKEN_TYPE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_exists = await get_user_by_id(db, user_id)

        if user_exists is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # Security: Check if user is still active
        if not user_exists.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

        return await create_user_tokens(user_id, db)

    except InvalidTokenError as e:
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


def decrypt_api_key(encrypted_api_key: str, settings_service: SettingsService, fernet_obj: Fernet | None = None) -> str:
    """Decrypt the provided encrypted API key using Fernet decryption.

    This function supports both encrypted and plain text values. It first attempts
    to decrypt the API key by encoding it, assuming it is a properly encrypted string.
    If that fails, it retries decryption using the original string input. If both
    decryption attempts fail, it checks if the value looks like a Fernet token
    (starts with "gAAAAA"). If it does, it's likely encrypted with a different key
    and returns empty string. Otherwise, it assumes plain text and returns as-is.

    Args:
        encrypted_api_key (str): The encrypted API key or plain text value.
        settings_service (SettingsService): Service providing authentication settings.
        fernet_obj (Fernet | None): Optional pre-initialized Fernet object.

    Returns:
        str: The decrypted API key, the original value if plain text, or empty string
             if it's encrypted with a different key.
    """
    fernet = fernet_obj
    if fernet is None:
        fernet = get_fernet(settings_service)

    if isinstance(encrypted_api_key, str):
        try:
            return fernet.decrypt(encrypted_api_key.encode()).decode()
        except Exception:  # noqa: BLE001
            try:
                return fernet.decrypt(encrypted_api_key).decode()
            except Exception as secondary_exception:  # noqa: BLE001
                # Check if this looks like a Fernet token (base64 encoded, starts with gAAAAA)
                if encrypted_api_key.startswith("gAAAAA"):
                    logger.warning(
                        "Failed to decrypt stored value (likely encrypted with different key). "
                        "Error: %s. Returning empty string.",
                        secondary_exception,
                    )
                    return ""

                # Assume the value is plain text and return it as-is
                return encrypted_api_key

    msg = "Unexpected variable type. Expected string"
    raise ValueError(msg)


# MCP-specific authentication functions that always behave as if skip_auth_auto_login is True
async def get_current_user_mcp(
    token: Annotated[str, Security(oauth2_login)],
    query_param: Annotated[str, Security(api_key_query)],
    header_param: Annotated[str, Security(api_key_header)],
    db: Annotated[AsyncSession, Depends(injectable_session_scope)],
) -> User:
    """MCP-specific user authentication that always allows fallback to username lookup.

    This function provides authentication for MCP endpoints with special handling:
    - If a JWT token is provided, it uses standard JWT authentication
    - If no API key is provided and AUTO_LOGIN is enabled, it falls back to
      username lookup using the configured superuser credentials
    - Otherwise, it validates the provided API key (from query param or header)
    """
    if token:
        return await get_current_user_by_jwt(token, db)

    # MCP-specific authentication logic - always behaves as if skip_auth_auto_login is True
    settings_service = get_settings_service()
    result: ApiKey | User | None

    if settings_service.auth_settings.AUTO_LOGIN:
        # Get the first user
        if not settings_service.auth_settings.SUPERUSER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing first superuser credentials",
            )
        if not query_param and not header_param:
            # For MCP endpoints, always fall back to username lookup when no API key is provided
            result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
            if result:
                logger.warning(AUTO_LOGIN_WARNING)
                return result
        else:
            result = await check_key(db, query_param or header_param)

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

    # If result is a User, return it directly
    if isinstance(result, User):
        return result

    # If result is an ApiKey, we need to get the associated user
    # This should not happen in normal flow, but adding for completeness
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid authentication result",
    )


async def get_current_active_user_mcp(current_user: Annotated[User, Depends(get_current_user_mcp)]):
    """MCP-specific active user dependency.

    This dependency is temporary and will be removed once MCP is fully integrated.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user
