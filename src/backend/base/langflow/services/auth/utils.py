from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Annotated, Final

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, WebSocket, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from lfx.log.logger import logger
from lfx.services.deps import injectable_session_scope,session_scope

from langflow.services.auth.service import (
    AUTO_LOGIN_ERROR as SERVICE_AUTO_LOGIN_ERROR,
)
from langflow.services.auth.service import (
    AUTO_LOGIN_WARNING as SERVICE_AUTO_LOGIN_WARNING,
)
from langflow.services.deps import get_auth_service

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import timedelta
    from uuid import UUID

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
    return get_auth_service()


AUTO_LOGIN_WARNING = SERVICE_AUTO_LOGIN_WARNING
AUTO_LOGIN_ERROR = SERVICE_AUTO_LOGIN_ERROR

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


async def get_current_user(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User:
    return await _auth_service().get_current_user(token, query_param, header_param, db)


async def get_current_user_from_access_token(
    token: str | Coroutine | None,
    db: AsyncSession,
) -> User:
    return await _auth_service().get_current_user_from_access_token(token, db)


async def get_current_user_for_websocket(
    websocket: WebSocket,
    db: AsyncSession,
) -> User | UserRead:
    token = websocket.cookies.get("access_token_lf") or websocket.query_params.get("token")
    api_key = (
        websocket.query_params.get("x-api-key")
        or websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key")
        or websocket.headers.get("api_key")
    )
    return await _auth_service().get_current_user_for_websocket(token, api_key, db)


async def get_current_user_for_sse(
    request: Request,
    db: AsyncSession = Depends(injectable_session_scope),
) -> User | UserRead:
    """Authenticate user for SSE endpoints.

    Similar to websocket authentication, accepts either:
    - Cookie authentication (access_token_lf)
    - API key authentication (x-api-key query param)

    Args:
        request: The FastAPI request object
        db: Database session

    Returns:
        User or UserRead: The authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    token = request.cookies.get("access_token_lf")
    api_key = request.query_params.get("x-api-key") or request.headers.get("x-api-key")
    return await _auth_service().get_current_user_for_sse(token, api_key, db)


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    return await _auth_service().get_current_active_user(user)


async def get_current_active_superuser(user: User = Depends(get_current_user)) -> User:
    return await _auth_service().get_current_active_superuser(user)


async def get_webhook_user(flow_id: str, request: Request) -> UserRead:
    return await _auth_service().get_webhook_user(flow_id, request)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _auth_service().verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _auth_service().get_password_hash(password)


def create_token(data: dict, expires_delta: timedelta) -> str:
    return _auth_service().create_token(data, expires_delta)


async def create_super_user(
    username: str,
    password: str,
    db: AsyncSession,
) -> User:
    return await _auth_service().create_super_user(username, password, db)


async def create_user_longterm_token(db: AsyncSession) -> tuple[UUID, dict]:
    return await _auth_service().create_user_longterm_token(db)


def create_user_api_key(user_id: UUID) -> dict:
    return _auth_service().create_user_api_key(user_id)


def get_user_id_from_token(token: str) -> UUID:
    return _auth_service().get_user_id_from_token(token)


async def create_user_tokens(user_id: UUID, db: AsyncSession, *, update_last_login: bool = False) -> dict:
    return await _auth_service().create_user_tokens(user_id, db, update_last_login=update_last_login)


async def create_refresh_token(refresh_token: str, db: AsyncSession) -> dict:
    return await _auth_service().create_refresh_token(refresh_token, db)


async def authenticate_user(username: str, password: str, db: AsyncSession) -> User | None:
    return await _auth_service().authenticate_user(username, password, db)


def get_fernet(settings_service: SettingsService):
    """Get a Fernet instance for encryption/decryption.
    
    Args:
        settings_service: Settings service to get the secret key
        
    Returns:
        Fernet instance for encryption/decryption
    """
    secret_key: str = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    
    # Ensure the key is valid for Fernet (32 url-safe base64-encoded bytes)
    if len(secret_key) < 32:  # noqa: PLR2004
        # Pad the key to 32 bytes
        secret_key = secret_key + "=" * (32 - len(secret_key))
    
    # Ensure it's properly base64 encoded
    try:
        base64.urlsafe_b64decode(secret_key)
        key = secret_key.encode()
    except Exception:  # noqa: BLE001
        # If not valid base64, encode it
        key = base64.urlsafe_b64encode(secret_key.encode()[:32])
    
    return Fernet(key)


def encrypt_api_key(api_key: str, settings_service: SettingsService | None = None) -> str:
    """Encrypt an API key.
    
    Args:
        api_key: The API key to encrypt
        settings_service: Settings service (unused, kept for backward compatibility)
        
    Returns:
        Encrypted API key string
    """
    return _auth_service().encrypt_api_key(api_key)


def decrypt_api_key(
    encrypted_api_key: str,
    settings_service: SettingsService | None = None,
    fernet_obj = None,
) -> str:
    """Decrypt an encrypted API key.
    
    Args:
        encrypted_api_key: The encrypted API key string
        settings_service: Settings service (unused, kept for backward compatibility)
        fernet_obj: Fernet object (unused, kept for backward compatibility)
        
    Returns:
        Decrypted API key string
    """
    return _auth_service().decrypt_api_key(encrypted_api_key)


async def get_current_user_mcp(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User:
    return await _auth_service().get_current_user_mcp(token, query_param, header_param, db)


async def get_current_active_user_mcp(user: User = Depends(get_current_user_mcp)) -> User:
    return await _auth_service().get_current_active_user_mcp(user)
