from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, Request, Security, WebSocket
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer

from langflow.services.auth.service import (
    AUTO_LOGIN_ERROR as SERVICE_AUTO_LOGIN_ERROR,
)
from langflow.services.auth.service import (
    AUTO_LOGIN_WARNING as SERVICE_AUTO_LOGIN_WARNING,
)
from langflow.services.deps import get_auth_service, get_session

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead

oauth2_login = OAuth2PasswordBearer(tokenUrl="api/v1/login", auto_error=False)

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
    db: Annotated[AsyncSession, Depends(get_session)],
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


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return await _auth_service().get_current_active_user(current_user)


async def get_current_active_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return await _auth_service().get_current_active_superuser(current_user)


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


def encrypt_api_key(api_key: str) -> str:
    return _auth_service().encrypt_api_key(api_key)


def decrypt_api_key(encrypted_api_key: str) -> str:
    return _auth_service().decrypt_api_key(encrypted_api_key)


async def get_current_user_mcp(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    return await _auth_service().get_current_user_mcp(token, query_param, header_param, db)


async def get_current_active_user_mcp(current_user: Annotated[User, Depends(get_current_user_mcp)]) -> User:
    return await _auth_service().get_current_active_user_mcp(current_user)
