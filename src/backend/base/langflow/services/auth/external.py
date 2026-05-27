from __future__ import annotations

import hashlib
import inspect
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, cast

import httpx
import jwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.services.auth.exceptions import InactiveUserError
from langflow.services.auth.exceptions import InvalidTokenError as AuthInvalidTokenError
from langflow.services.database.models.auth import SSOUserProfile
from langflow.services.database.models.user.crud import get_user_by_id, get_user_by_username, update_user_last_login_at
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings
    from sqlmodel.ext.asyncio.session import AsyncSession


JWKS_CACHE_TTL_SECONDS = 300
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
T = TypeVar("T")


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    subject: str
    username: str
    email: str | None
    name: str | None
    claims: dict[str, Any]


class ExternalIdentityResolver(Protocol):
    async def resolve(self, token: str, auth_settings: AuthSettings) -> ExternalIdentity | dict[str, Any]: ...


ExternalResolverResult: TypeAlias = ExternalIdentity | dict[str, Any]
ExternalResolverCallable: TypeAlias = Callable[
    [str, "AuthSettings"],
    ExternalResolverResult | Awaitable[ExternalResolverResult],
]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _claim_as_str(claims: dict[str, Any], claim_name: str | None) -> str | None:
    if not claim_name:
        return None
    value = claims.get(claim_name)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if value is None:
        return None
    return str(value)


def _normalize_username(value: str) -> str:
    username = value.strip()
    if not username:
        return "external-user"
    return username[:255]


def _external_username_fallback(provider: str, subject: str) -> str:
    digest = hashlib.sha256(f"{provider}:{subject}".encode()).hexdigest()[:12]
    normalized_provider = provider[:200] or "external"
    return f"{normalized_provider}-{digest}"


def _identity_from_claims(claims: dict[str, Any], auth_settings: AuthSettings) -> ExternalIdentity:
    provider = (auth_settings.EXTERNAL_AUTH_PROVIDER or "external").strip() or "external"
    subject = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_SUBJECT_CLAIM)
    if not subject:
        msg = f"External credential is missing required claim: {auth_settings.EXTERNAL_AUTH_SUBJECT_CLAIM}"
        raise AuthInvalidTokenError(msg)

    email = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_EMAIL_CLAIM)
    preferred_username = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_USERNAME_CLAIM)
    name = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_NAME_CLAIM)
    username_claim = preferred_username or email or name or _external_username_fallback(provider, subject)
    username = _normalize_username(username_claim)

    return ExternalIdentity(
        provider=provider,
        subject=subject,
        username=username,
        email=email,
        name=name,
        claims=claims,
    )


def _validate_trusted_time_claims(claims: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).timestamp()
    exp = claims.get("exp")
    if exp is not None and now > float(exp):
        msg = "External credential has expired"
        raise AuthInvalidTokenError(msg)

    nbf = claims.get("nbf")
    if nbf is not None and now < float(nbf):
        msg = "External credential is not valid yet"
        raise AuthInvalidTokenError(msg)


async def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    cached = _jwks_cache.get(jwks_url)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()

    _jwks_cache[jwks_url] = (now + JWKS_CACHE_TTL_SECONDS, jwks)
    return jwks


def _select_jwk(jwks: dict[str, Any], token: str) -> dict[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        msg = "External JWKS does not contain signing keys"
        raise AuthInvalidTokenError(msg)

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if kid:
        for key in keys:
            if key.get("kid") == kid:
                return key
        msg = "External JWT signing key was not found in JWKS"
        raise AuthInvalidTokenError(msg)

    if len(keys) == 1:
        return keys[0]

    msg = "External JWT is missing kid and JWKS contains multiple keys"
    raise AuthInvalidTokenError(msg)


async def decode_external_jwt(token: str, auth_settings: AuthSettings) -> dict[str, Any]:
    if not auth_settings.EXTERNAL_AUTH_ENABLED:
        msg = "External authentication is not enabled"
        raise AuthInvalidTokenError(msg)

    try:
        if auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE:
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                },
            )
            _validate_trusted_time_claims(claims)
            return claims

        if not auth_settings.EXTERNAL_AUTH_JWKS_URL:
            msg = "External authentication requires EXTERNAL_AUTH_JWKS_URL unless trusted decode is enabled"
            raise AuthInvalidTokenError(msg)

        jwks = await _fetch_jwks(auth_settings.EXTERNAL_AUTH_JWKS_URL)
        jwk = _select_jwk(jwks, token)
        signing_key = jwt.PyJWK.from_dict(jwk).key
        audience = _split_csv(auth_settings.EXTERNAL_AUTH_AUDIENCE)
        issuer = auth_settings.EXTERNAL_AUTH_ISSUER or None
        algorithms = _split_csv(auth_settings.EXTERNAL_AUTH_ALGORITHMS) or ["RS256"]

        return jwt.decode(
            token,
            signing_key,
            algorithms=algorithms,
            audience=audience if audience else None,
            issuer=issuer,
            options={
                "verify_aud": bool(audience),
                "verify_iss": bool(issuer),
            },
        )
    except AuthInvalidTokenError:
        raise
    except PyJWTInvalidTokenError as exc:
        msg = "External credential validation failed"
        raise AuthInvalidTokenError(msg) from exc
    except Exception as exc:
        logger.debug(f"External credential validation failed: {exc}")
        msg = "External credential validation failed"
        raise AuthInvalidTokenError(msg) from exc


async def resolve_external_identity(token: str, auth_settings: AuthSettings) -> ExternalIdentity:
    resolver = _load_external_identity_resolver(auth_settings)
    if hasattr(resolver, "resolve"):
        result = await _maybe_await(resolver.resolve(token, auth_settings))
    elif callable(resolver):
        result = await _maybe_await(resolver(token, auth_settings))
    else:
        msg = "External authentication resolver must be callable or expose resolve()"
        raise AuthInvalidTokenError(msg)

    if isinstance(result, ExternalIdentity):
        return result
    if isinstance(result, dict):
        return _identity_from_claims(result, auth_settings)

    msg = "External authentication resolver returned an invalid identity"
    raise AuthInvalidTokenError(msg)


class JwtExternalIdentityResolver:
    async def resolve(self, token: str, auth_settings: AuthSettings) -> ExternalIdentity:
        claims = await decode_external_jwt(token, auth_settings)
        return _identity_from_claims(claims, auth_settings)


def _load_external_identity_resolver(
    auth_settings: AuthSettings,
) -> ExternalIdentityResolver | ExternalResolverCallable:
    resolver_path = auth_settings.EXTERNAL_AUTH_IDENTITY_RESOLVER
    if not resolver_path:
        return JwtExternalIdentityResolver()

    from lfx.services.config_discovery import load_object_from_import_path

    resolver = load_object_from_import_path(
        resolver_path,
        object_kind="external auth resolver",
        object_key="EXTERNAL_AUTH_IDENTITY_RESOLVER",
    )
    if resolver is None:
        msg = "External authentication resolver could not be loaded"
        raise AuthInvalidTokenError(msg)

    if inspect.isclass(resolver):
        signature = inspect.signature(resolver)
        required_params = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if required_params:
            return resolver(auth_settings)
        return resolver()

    return resolver


async def _maybe_await(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await cast("Awaitable[T]", value)
    return value


async def _unique_username(db: AsyncSession, desired_username: str, provider: str, subject: str) -> str:
    username = _normalize_username(desired_username)
    existing = await get_user_by_username(db, username)
    if existing is None:
        return username

    fallback = _external_username_fallback(provider, subject)
    if await get_user_by_username(db, fallback) is None:
        return fallback

    digest = hashlib.sha256(f"{provider}:{subject}:{username}".encode()).hexdigest()[:16]
    return f"{provider}-{digest}"


async def _initialize_jit_user_defaults(user: User, db: AsyncSession) -> None:
    from langflow.initial_setup.setup import get_or_create_default_folder
    from langflow.services.deps import get_variable_service

    await get_or_create_default_folder(db, user.id)
    await get_variable_service().initialize_user_variables(user.id, db)


async def get_or_create_external_user(
    *,
    token: str,
    db: AsyncSession,
    auth_settings: AuthSettings,
    password_hasher,
) -> User:
    identity = await resolve_external_identity(token, auth_settings)

    profile_stmt = select(SSOUserProfile).where(
        SSOUserProfile.sso_provider == identity.provider,
        SSOUserProfile.sso_user_id == identity.subject,
    )
    profile = (await db.exec(profile_stmt)).first()

    if profile:
        user = await get_user_by_id(db, profile.user_id)
        if user is None:
            msg = "Mapped external user was not found"
            raise AuthInvalidTokenError(msg)
        if not user.is_active:
            msg = "User account is inactive"
            raise InactiveUserError(msg)

        profile.email = identity.email
        profile.sso_last_login_at = datetime.now(timezone.utc)
        profile.updated_at = datetime.now(timezone.utc)
        await update_user_last_login_at(user.id, db)
        return user

    username = await _unique_username(db, identity.username, identity.provider, identity.subject)
    user = User(
        username=username,
        password=password_hasher(secrets.token_urlsafe(48)),
        is_active=True,
        is_superuser=False,
        last_login_at=datetime.now(timezone.utc),
    )
    profile = SSOUserProfile(
        user_id=user.id,
        sso_provider=identity.provider,
        sso_user_id=identity.subject,
        email=identity.email,
        sso_last_login_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.add(profile)
    try:
        await db.flush()
        await db.refresh(user)
        await _initialize_jit_user_defaults(user, db)
    except IntegrityError:
        await db.rollback()
        profile = (await db.exec(profile_stmt)).first()
        if profile is None:
            raise
        user = await get_user_by_id(db, profile.user_id)
        if user is None:
            msg = "Mapped external user was not found"
            raise AuthInvalidTokenError(msg) from None
        if not user.is_active:
            msg = "User account is inactive"
            raise InactiveUserError(msg) from None

    return user


def extract_bearer_or_raw_token(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    scheme, _, token = stripped.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip() or None
    return stripped


def extract_external_token(headers: Any, cookies: Any, auth_settings: AuthSettings) -> str | None:
    if not auth_settings.EXTERNAL_AUTH_ENABLED:
        return None

    header_name = auth_settings.EXTERNAL_AUTH_TOKEN_HEADER
    if header_name:
        header_value = headers.get(header_name)
        if token := extract_bearer_or_raw_token(header_value):
            return token

    cookie_name = auth_settings.EXTERNAL_AUTH_TOKEN_COOKIE
    if cookie_name:
        cookie_value = cookies.get(cookie_name)
        if token := extract_bearer_or_raw_token(cookie_value):
            return token

    return None
