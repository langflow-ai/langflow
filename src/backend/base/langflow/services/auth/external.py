"""External trusted-identity helpers.

When an upstream identity layer (proxy, gateway, IdP) issues or validates a
credential, Langflow accepts it via this module: extract the token from the
configured header/cookie, validate it (built-in JWT/JWKS or a pluggable
resolver), and return a normalized :class:`ExternalIdentity`. JIT user
provisioning is handled separately by
``BaseAuthService.get_or_create_user_from_claims`` so the auth service stays
the single source of truth for user lifecycle.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, cast

import httpx
import jwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError
from lfx.log.logger import logger

from langflow.services.auth.exceptions import InvalidTokenError as AuthInvalidTokenError

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings


JWKS_CACHE_TTL_SECONDS = 300
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
T = TypeVar("T")


@dataclass(frozen=True)
class ExternalIdentity:
    """Normalized identity returned by an :class:`ExternalIdentityResolver`."""

    provider: str
    subject: str
    username: str
    email: str | None = None
    name: str | None = None
    claims: Mapping[str, Any] = field(default_factory=dict)


class ExternalIdentityResolver(Protocol):
    """Resolver that turns an external credential into an identity."""

    async def resolve(
        self,
        token: str,
        auth_settings: AuthSettings,
    ) -> ExternalIdentity | Mapping[str, Any]: ...


ExternalResolverResult: TypeAlias = ExternalIdentity | Mapping[str, Any]
ExternalResolverCallable: TypeAlias = Callable[
    [str, "AuthSettings"],
    ExternalResolverResult | Awaitable[ExternalResolverResult],
]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _claim_as_str(claims: Mapping[str, Any], claim_name: str | None) -> str | None:
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


def identity_from_claims(claims: Mapping[str, Any], auth_settings: AuthSettings) -> ExternalIdentity:
    """Build an :class:`ExternalIdentity` from raw JWT claims using the configured mapping."""
    provider = (auth_settings.EXTERNAL_AUTH_PROVIDER or "external").strip() or "external"
    subject = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_SUBJECT_CLAIM)
    if not subject:
        msg = f"External credential is missing required claim: {auth_settings.EXTERNAL_AUTH_SUBJECT_CLAIM}"
        raise AuthInvalidTokenError(msg)

    email = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_EMAIL_CLAIM)
    preferred_username = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_USERNAME_CLAIM)
    name = _claim_as_str(claims, auth_settings.EXTERNAL_AUTH_NAME_CLAIM)
    username_claim = preferred_username or email or name or _external_username_fallback(provider, subject)

    return ExternalIdentity(
        provider=provider,
        subject=subject,
        username=_normalize_username(username_claim),
        email=email,
        name=name,
        claims=dict(claims),
    )


def _validate_trusted_time_claims(claims: Mapping[str, Any]) -> None:
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
    """Validate an external JWT and return its claims.

    If ``EXTERNAL_AUTH_TRUSTED_JWT_DECODE`` is enabled, signature verification
    is skipped (the caller has stated an upstream proxy already validated it).
    Otherwise ``EXTERNAL_AUTH_JWKS_URL`` is required and the signature is
    verified against the fetched JWKS using ``EXTERNAL_AUTH_ALGORITHMS``.
    ``exp`` / ``nbf`` are always checked.
    """
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


class JwtExternalIdentityResolver:
    """Default resolver: validate the credential as a JWT and map claims."""

    async def resolve(self, token: str, auth_settings: AuthSettings) -> ExternalIdentity:
        claims = await decode_external_jwt(token, auth_settings)
        return identity_from_claims(claims, auth_settings)


async def resolve_external_identity(token: str, auth_settings: AuthSettings) -> ExternalIdentity:
    """Resolve a credential to an :class:`ExternalIdentity` using the configured resolver."""
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
    if isinstance(result, Mapping):
        return identity_from_claims(result, auth_settings)

    msg = "External authentication resolver returned an invalid identity"
    raise AuthInvalidTokenError(msg)


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
    return cast("T", value)


def extract_bearer_or_raw_token(value: str | None) -> str | None:
    """Strip a 'Bearer ' prefix if present and return the credential."""
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    scheme, _, token = stripped.partition(" ")
    if scheme.lower() == "bearer":
        return token.strip() or None
    return stripped


def extract_external_token(
    headers: Mapping[str, str],
    cookies: Mapping[str, str],
    auth_settings: AuthSettings,
) -> str | None:
    """Return the external credential from configured header/cookie, header first."""
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
