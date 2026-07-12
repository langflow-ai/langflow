from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Annotated, Final

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, WebSocket, WebSocketException, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from lfx.log.logger import logger
from lfx.services.deps import get_auth_service, injectable_session_scope, session_scope

from services.auth.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    MissingCredentialsError,
)
from services.auth.external import extract_external_token
from services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import timedelta

    from lfx.services.database.models.user import User, UserRead
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


class OAuth2PasswordBearerCookie(OAuth2PasswordBearer):
    """Custom OAuth2 scheme that checks Authorization header first, then cookies.

    This allows the application to work with HttpOnly cookies while supporting
    explicit Authorization headers for backward compatibility and testing scenarios.
    If an explicit Authorization header is provided, it takes precedence over cookies.
    When external trusted auth is enabled, the configured external header/cookie
    is consulted last so the native JWT path is always tried first.
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

        # Final fallback: external trusted credential (validated downstream).
        if external := _get_external_token(request.headers, request.cookies):
            return external

        # If auto_error is True, this would raise an exception
        # Since we set auto_error=False, return None
        return None


def _get_external_token(headers, cookies) -> str | None:
    """Return the configured external credential, swallowing transient failures."""
    try:
        auth_settings = get_settings_service().auth_settings
    except Exception:  # noqa: BLE001
        return None
    return extract_external_token(headers, cookies, auth_settings)


oauth2_login = OAuth2PasswordBearerCookie(tokenUrl="api/v1/login", auto_error=False)

API_KEY_NAME = "x-api-key"  # pragma: allowlist secret

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
    request: Request,
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User:
    # Keep the native token (resolved by oauth2_login, which may already have
    # collapsed to the external credential) separate from a freshly-extracted
    # external credential so a present-but-invalid native cookie cannot shadow a
    # valid external one. The auth service tries the native token first and only
    # falls back to the external credential when it differs from the token.
    external_token = _get_external_token(request.headers, request.cookies)
    try:
        return await _auth_service().get_current_user(
            token, query_param, header_param, db, external_token=external_token
        )
    except AuthenticationError as e:
        raise _auth_error_to_http(e) from e


async def get_current_user_from_access_token(
    token: str | Coroutine | None,
    db: AsyncSession,
    external_token: str | None = None,
) -> User:
    """Compatibility helper to resolve a user from an access token.

    This simply delegates to the active auth service's
    `get_current_user_from_access_token` implementation. ``external_token`` is an
    optional, separately-extracted external credential tried as a fallback when
    native token authentication fails; when ``None`` behavior is unchanged.

    **For new code, prefer calling
    `get_auth_service().get_current_user_from_access_token(...)` directly**
    instead of importing this function.
    """
    try:
        return await _auth_service().get_current_user_from_access_token(token, db, external_token=external_token)
    except AuthenticationError as e:
        raise _auth_error_to_http(e) from e


WS_AUTH_REASON = "Missing or invalid credentials (cookie, token or API key)."


async def get_current_user_for_websocket(
    websocket: WebSocket,
    db: AsyncSession,
) -> User | UserRead:
    """Extracts credentials from WebSocket and delegates to auth service."""
    # Keep the native token and the external credential separate so a present but
    # invalid/expired native token cannot shadow a valid external credential; the
    # auth service tries the external token as a fallback when native auth fails.
    token = websocket.cookies.get("access_token_lf") or websocket.query_params.get("token")
    external_token = _get_external_token(websocket.headers, websocket.cookies)
    api_key = (
        websocket.query_params.get("x-api-key")
        or websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key")
        or websocket.headers.get("api_key")
    )

    try:
        return await _auth_service().get_current_user_for_websocket(token, api_key, db, external_token=external_token)
    except AuthenticationError as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=WS_AUTH_REASON) from e


async def get_current_user_for_sse(
    request: Request,
    db: AsyncSession = Depends(injectable_session_scope),
) -> User | UserRead:
    """Extracts credentials from request and delegates to auth service.

    Accepts cookie (access_token_lf) or API key (x-api-key query param).
    """
    # Keep the native token and the external credential separate (see
    # get_current_user_for_websocket) so the external credential remains a usable
    # fallback even when a stale native cookie is present.
    token = request.cookies.get("access_token_lf")
    external_token = _get_external_token(request.headers, request.cookies)
    api_key = request.query_params.get("x-api-key") or request.headers.get("x-api-key")

    try:
        return await _auth_service().get_current_user_for_sse(token, api_key, db, external_token=external_token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid credentials (cookie or API key).",
        ) from e


async def get_current_user_for_workflow(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
) -> UserRead:
    """Combined session-or-API-key auth that does not hold a DB session.

    Resolves the user from a session cookie/token *or* an API key inside a
    short-lived session that is committed and closed before the path operation
    runs. Unlike `get_current_active_user` (a generator dependency whose session
    stays open for the whole request), this is required by endpoints that
    execute a graph inline: a held auth connection contends with the run's own
    writes (on SQLite it blocks the run's INSERTs with "database is locked").
    """
    from lfx.services.database.models.user import UserRead

    async with session_scope() as db:
        try:
            user = await _auth_service().get_current_user(token, query_param, header_param, db)
        except AuthenticationError as e:
            raise _auth_error_to_http(e) from e
        active_user = await _auth_service().get_current_active_user(user)
        if active_user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        return UserRead.model_validate(active_user, from_attributes=True)


async def get_optional_user(
    token: Annotated[str | None, Security(oauth2_login)],
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(injectable_session_scope),
) -> User | None:
    """Get the current user if authenticated, otherwise return None.

    This is useful for endpoints that need to behave differently for authenticated
    vs unauthenticated users (e.g., returning different response types).

    Returns:
        User | None: The authenticated user if valid credentials are provided, None otherwise.
    """
    try:
        user = await _auth_service().get_current_user(token, query_param, header_param, db)
    except (AuthenticationError, HTTPException):
        return None
    else:
        if user and user.is_active:
            return user
        return None


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
    return await _auth_service().get_webhook_user(flow_id, request)


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(injectable_session_scope),
) -> User | None:
    """Resolve the current user if authenticated, otherwise return None.

    Checks HttpOnly cookie (access_token_lf), Authorization header, and API key.
    Used by endpoints that support both authenticated and unauthenticated access.
    """
    token = request.cookies.get("access_token_lf")
    api_key = request.query_params.get("x-api-key") or request.headers.get("x-api-key")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = token or auth_header[len("Bearer ") :]

    # Keep the external credential separate so it remains a usable fallback when a
    # stale/invalid native token is present (see get_current_user_for_websocket).
    external_token = _get_external_token(request.headers, request.cookies)

    if not token and not external_token and not api_key:
        return None

    try:
        return await _auth_service().get_current_user_for_sse(token, api_key, db, external_token=external_token)
    except (AuthenticationError, HTTPException):
        return None


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


def add_base64_padding(value: str) -> str:
    """Add base64 padding characters if needed.

    Base64 strings must have a length that is a multiple of 4.
    This adds the necessary '=' padding characters.
    """
    remainder = len(value) % 4
    if remainder == 0:
        return value
    return value + "=" * (4 - remainder)


def ensure_fernet_key(secret_key: str) -> bytes:
    """Derive a valid Fernet key from a secret key string.

    For short keys (< 32 chars), the 32-byte key is derived with SHA-256, a
    cryptographic hash. For longer keys, base64 padding is added.

    Security note: short keys previously seeded Python's ``random`` module
    (``random.seed(secret_key)``) to generate the key bytes. ``random`` is a
    non-cryptographic Mersenne-Twister PRNG, so the resulting Fernet key was
    fully predictable from the secret, and seeding it also mutated global PRNG
    state. SHA-256 is deterministic (so the key stays stable for a given
    secret) but is not predictable/reversible the way the PRNG output was.

    Deployments that set a ``SECRET_KEY`` shorter than 32 characters will derive
    a different key than before this fix and must re-enter encrypted secrets
    (API keys, global variables) after upgrading. The default ``SECRET_KEY`` is
    a 43-char ``secrets.token_urlsafe(32)`` value and is unaffected.
    """
    MINIMUM_KEY_LENGTH = 32  # noqa: N806
    if len(secret_key) < MINIMUM_KEY_LENGTH:
        digest = hashlib.sha256(secret_key.encode()).digest()  # 32 bytes
        key = base64.urlsafe_b64encode(digest)
    else:
        key = add_base64_padding(secret_key).encode()
    return key


def get_fernet(settings_service: SettingsService) -> Fernet:
    """Get a Fernet instance for encryption/decryption.

    Args:
        settings_service: Settings service to get the secret key

    Returns:
        Fernet instance for encryption/decryption
    """
    secret_key: str = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    return Fernet(ensure_fernet_key(secret_key))


def encrypt_api_key(api_key: str, settings_service: SettingsService | None = None) -> str:  # noqa: ARG001
    return _auth_service().encrypt_api_key(api_key)


def decrypt_api_key(
    encrypted_api_key: str,
    settings_service: SettingsService | None = None,  # noqa: ARG001
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
