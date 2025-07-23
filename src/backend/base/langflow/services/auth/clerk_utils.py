import uuid
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwk, jwt
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.logging.logger import logger
from langflow.services.database.models.user import User, UserCreate
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_settings_service

# Context variable to store decoded clerk claims per request
auth_header_ctx: ContextVar[dict | None] = ContextVar("auth_header_ctx", default=None)

_jwks_cache: dict[str, dict[str, Any]] = {}

# APIs that require Clerk token decoding in middleware
PROTECTED_PATHS = ["/api/v1/users/","/api/v1/login/"]


async def _get_jwks(issuer: str) -> dict[str, Any]:
    """Retrieve and cache JWKS for a Clerk issuer."""
    issuer = issuer.rstrip("/")
    if issuer not in _jwks_cache:
        url = f"{issuer}/.well-known/jwks.json"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        _jwks_cache[issuer] = {k["kid"]: k for k in data.get("keys", [])}
    return _jwks_cache[issuer]


async def verify_clerk_token(token: str) -> dict[str, Any]:
    """Verify a Clerk token, add a UUID derived from the Clerk ID, and return the payload."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)
        issuer: str | None = unverified_claims.get("iss")
        kid: str | None = unverified_header.get("kid")
        if not issuer or not kid:
            msg = "Missing issuer or kid"
            raise JWTError(msg)
        jwks = await _get_jwks(issuer)
        key = jwks.get(kid)
        if not key:
            _jwks_cache.pop(issuer, None)  # force refresh
            jwks = await _get_jwks(issuer)
            key = jwks.get(kid)
            if not key:
                msg = "Public key not found"
                raise JWTError(msg)

        public_key = jwk.construct(key, unverified_header.get("alg", "RS256"))
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[unverified_header.get("alg", "RS256")],
            audience=unverified_claims.get("aud"),
            issuer=issuer,
        )
        # ✅ Add deterministic UUID to the payload
        clerk_id = payload.get("sub")
        if not clerk_id:
            msg = "Missing 'sub' (Clerk ID) in token payload"
            raise JWTError(msg)
        payload["uuid"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(clerk_id)))

    except JWTError as exc:
        msg = "Invalid token"
        raise ValueError(msg) from exc
    return payload


async def process_new_user_with_clerk(_user: UserCreate, new_user: User):
    settings = get_settings_service().auth_settings
    # ✅ If Clerk is enabled, pull UUID from enriched auth_header_ctx payload
    if settings.CLERK_AUTH_ENABLED:
        payload = auth_header_ctx.get()
        if not payload:
            raise HTTPException(status_code=401, detail="Missing Clerk payload")
        clerk_uuid = payload.get("uuid")
        if not clerk_uuid:
            raise HTTPException(status_code=401, detail="Missing Clerk UUID")
        new_user.id = UUID(clerk_uuid)
        logger.info(f"[process_new_user_with_clerk] Assigned Clerk UUID {new_user.id} to new user object")

async def get_user_from_clerk_payload(token: str, db: AsyncSession) -> User:
    """Retrieve the current user using the payload from ``verify_clerk_token``."""
    try:
        payload = await verify_clerk_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    uuid_str = payload.get("uuid")
    logger.info(f"uuid_str: {uuid_str}")
    if not uuid_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Clerk UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(uuid_str)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk UUID format",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    user = await get_user_by_id(db, user_id)
    logger.info(f"Retrieved user: {user}")
    if user is None:
        logger.info("User not found.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.info(f"User {user.id} is inactive.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def clerk_token_middleware(request: Request, call_next):
    """Middleware to decode Clerk token for specific paths."""
    settings = get_settings_service()

    ctx_token: Token | None = None
    if settings.auth_settings.CLERK_AUTH_ENABLED and request.url.path in PROTECTED_PATHS:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :]
            try:
                payload = await verify_clerk_token(token)
                ctx_token = auth_header_ctx.set(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to verify Clerk token: {exc}")

    try:
        return await call_next(request)
    finally:
        if ctx_token is not None:
            auth_header_ctx.reset(ctx_token)
        else:
            auth_header_ctx.set(None)
