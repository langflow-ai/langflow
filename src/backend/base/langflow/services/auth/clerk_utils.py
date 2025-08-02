import uuid
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwk, jwt
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from langflow.logging.logger import logger
from langflow.services.database.models.user import User
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_settings_service

# Context variable to store decoded clerk claims per request
auth_header_ctx: ContextVar[dict | None] = ContextVar("auth_header_ctx", default=None)

_jwks_cache: dict[str, dict[str, Any]] = {}


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


def get_user_id_from_clerk_payload() -> UUID:
    """Extract the Clerk user UUID from the request context."""
    payload = auth_header_ctx.get()
    if not payload:
        raise HTTPException(status_code=401, detail="Missing Clerk payload")
    clerk_uuid = payload.get("uuid")
    if not clerk_uuid:
        raise HTTPException(status_code=401, detail="Missing Clerk UUID")
    try:
        return UUID(clerk_uuid)
    except ValueError as err:
        raise HTTPException(
            status_code=401,
            detail="Invalid Clerk UUID format",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


async def process_new_user_with_clerk(new_user: User):
    settings = get_settings_service().auth_settings
    # ✅ If Clerk is enabled, pull UUID from enriched auth_header_ctx payload
    if settings.CLERK_AUTH_ENABLED:
        user_id = get_user_id_from_clerk_payload()
        new_user.id = user_id
        logger.info(f"[process_new_user_with_clerk] Assigned Clerk UUID {new_user.id} to new user object")


async def get_user_from_clerk_payload(db: AsyncSession) -> User:
    """Retrieve the current user using the payload stored in the request context."""
    user_id = get_user_id_from_clerk_payload()
    logger.debug(f"uuid_str: {user_id}")

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
    """Middleware to decode Clerk token when present."""
    settings = get_settings_service()
    if not settings.auth_settings.CLERK_AUTH_ENABLED:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return await call_next(request)

    ctx_token: Token | None = None
    token = auth_header[len("Bearer ") :]
    try:
        payload = await verify_clerk_token(token)
        ctx_token = auth_header_ctx.set(payload)
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to verify Clerk token: {exc}")
        return JSONResponse(
            status_code=HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid Clerk token"},
        )
    finally:
        if ctx_token is not None:
            auth_header_ctx.reset(ctx_token)
        else:
            auth_header_ctx.set(None)
    return response
