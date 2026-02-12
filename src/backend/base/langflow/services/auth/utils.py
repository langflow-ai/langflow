from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Annotated, Final

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, WebSocket, WebSocketException, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from lfx.log.logger import logger
from lfx.services.deps import injectable_session_scope

from langflow.services.auth.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    MissingCredentialsError,
)
from langflow.services.deps import get_auth_service

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import timedelta

    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


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


def _auth_service():
    """Return the currently configured auth service.

    This is an internal helper to keep imports local to the auth services layer.
    **New code should prefer calling `get_auth_service()` directly** instead of
    using this helper or adding new thin wrapper functions here.
    """
    return get_auth_service()


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


async def api_key_security(
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
) -> UserRead | None:
    return await _auth_service().api_key_security(query_param, header_param)


async def ws_api_key_security(api_key: str | None) -> UserRead:
    return await _auth_service().ws_api_key_security(api_key)


def _auth_error_to_http(e: AuthenticationError) -> HTTPException:
    """Map auth exceptions to 401 Unauthorized or 403 Forbidden.

    Langflow returns 403 for missing/invalid credentials; 401 for invalid/expired tokens.
    """
    if isinstance(
        e,
        (MissingCredentialsError, InvalidCredentialsError, InsufficientPermissionsError),
    ):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


async def get_current_user(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User:
    try:
        return await _auth_service().get_current_user(token, query_param, header_param, db)
    except AuthenticationError as e:
        raise _auth_error_to_http(e) from e


async def get_current_user_from_access_token(
    token: str | Coroutine | None,
    db: AsyncSession,
) -> User:
    """Compatibility helper to resolve a user from an access token.

    This simply delegates to the active auth service's
    `get_current_user_from_access_token` implementation.

    **For new code, prefer calling
    `get_auth_service().get_current_user_from_access_token(...)` directly**
    instead of importing this function.
    """
    try:
        return await _auth_service().get_current_user_from_access_token(token, db)
    except AuthenticationError as e:
        raise _auth_error_to_http(e) from e


WS_AUTH_REASON = "Missing or invalid credentials (cookie, token or API key)."


async def get_current_user_for_websocket(
    websocket: WebSocket,
    db: AsyncSession,
) -> User | UserRead:
    """Extracts credentials from WebSocket and delegates to auth service."""
    token = websocket.cookies.get("access_token_lf") or websocket.query_params.get("token")
    api_key = (
        websocket.query_params.get("x-api-key")
        or websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key")
        or websocket.headers.get("api_key")
    )

    try:
        return await _auth_service().get_current_user_for_websocket(token, api_key, db)
    except AuthenticationError as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=WS_AUTH_REASON) from e


async def get_current_user_for_sse(
    request: Request,
    db: AsyncSession = Depends(injectable_session_scope),
) -> User | UserRead:
    """Extracts credentials from request and delegates to auth service.

    Accepts cookie (access_token_lf) or API key (x-api-key query param).
    """
    token = request.cookies.get("access_token_lf")
    api_key = request.query_params.get("x-api-key") or request.headers.get("x-api-key")

    try:
        return await _auth_service().get_current_user_for_sse(token, api_key, db)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid credentials (cookie or API key).",
        ) from e


async def get_current_active_user(user: User = Depends(get_current_user)) -> User | UserRead:
    result = await _auth_service().get_current_active_user(user)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return result


async def get_current_active_superuser(user: User = Depends(get_current_user)) -> User | UserRead:
    result = await _auth_service().get_current_active_superuser(user)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return result


def get_fernet(settings_service: SettingsService) -> Fernet:
    """Get a Fernet instance for encryption/decryption.

    Args:
        settings_service: Settings service to get the secret key

    Returns:
        Fernet instance for encryption/decryption
    """
    import random

    secret_key: str = settings_service.auth_settings.SECRET_KEY.get_secret_value()

    # Replicate the original _ensure_valid_key logic from AuthService
    MINIMUM_KEY_LENGTH = 32  # noqa: N806
    if len(secret_key) < MINIMUM_KEY_LENGTH:
        # Generate deterministic key from seed for short keys
        random.seed(secret_key)
        key = bytes(random.getrandbits(8) for _ in range(32))
        key = base64.urlsafe_b64encode(key)
    else:
        # Add padding for longer keys
        padding_needed = 4 - len(secret_key) % 4
        padded_key = secret_key + "=" * padding_needed
        key = padded_key.encode()

    return Fernet(key)


def encrypt_api_key(api_key: str, settings_service: SettingsService | None = None) -> str:  # noqa: ARG001
    return _auth_service().encrypt_api_key(api_key)


def decrypt_api_key(
    encrypted_api_key: str,
    settings_service: SettingsService | None = None,  # noqa: ARG001
    fernet_obj=None,  # noqa: ARG001
) -> str:
    return _auth_service().decrypt_api_key(encrypted_api_key)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _auth_service().verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _auth_service().get_password_hash(password)


def create_token(data: dict, expires_delta: timedelta) -> str:
    """Create a JWT token. Delegates to the active auth service."""
    return _auth_service().create_token(data, expires_delta)


async def create_refresh_token(refresh_token: str, db: AsyncSession) -> dict:
    """Exchange a refresh token for new access/refresh tokens. Delegates to the active auth service."""
    return await _auth_service().create_refresh_token(refresh_token, db)


async def create_super_user(username: str, password: str, db: AsyncSession) -> User:
    return await _auth_service().create_super_user(username, password, db)


async def create_user_longterm_token(db: AsyncSession) -> tuple:
    return await _auth_service().create_user_longterm_token(db)


async def get_current_user_mcp(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User:
    try:
        return await _auth_service().get_current_user_mcp(token, query_param, header_param, db)
    except AuthenticationError as e:
        raise _auth_error_to_http(e) from e


async def get_current_active_user_mcp(user: User = Depends(get_current_user_mcp)) -> User:
    return await _auth_service().get_current_active_user_mcp(user)
