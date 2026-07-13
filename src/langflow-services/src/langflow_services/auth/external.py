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
import json
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, cast
from urllib.parse import urlparse

import httpx
import jwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError
from lfx.log.logger import logger

from langflow_services.auth.exceptions import InvalidTokenError as AuthInvalidTokenError

# The request-scoped access ceiling is an authorization primitive. It lives in
# the authorization package so guards can enforce it without importing the auth
# layer; the auth layer (here) only *derives* the ceiling from an identity and
# installs it. These re-exports keep ``langflow.services.auth.external`` a stable
# import site for callers that derive/inspect the ceiling.
from langflow_services.authorization.access_ceiling import (
    EXTERNAL_ACCESS_ADMIN,
    EXTERNAL_ACCESS_EDITOR,
    EXTERNAL_ACCESS_LEVELS,
    EXTERNAL_ACCESS_VIEWER,
    ExternalAccessContext,
    clear_current_external_access_context,
    external_access_allows,
    filter_actions_by_external_access_ceiling,
    get_current_external_access_context,
    set_current_external_access_context,
)

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings

__all__ = [
    "EXTERNAL_ACCESS_ADMIN",
    "EXTERNAL_ACCESS_EDITOR",
    "EXTERNAL_ACCESS_LEVELS",
    "EXTERNAL_ACCESS_VIEWER",
    "ExternalAccessContext",
    "ExternalIdentity",
    "ExternalIdentityResolver",
    "JwtExternalIdentityResolver",
    "access_context_from_identity",
    "clear_current_external_access_context",
    "decode_external_jwt",
    "external_access_allows",
    "extract_bearer_or_raw_token",
    "extract_external_token",
    "filter_actions_by_external_access_ceiling",
    "get_current_external_access_context",
    "identity_from_claims",
    "resolve_external_identity",
    "set_current_external_access_context",
]


JWKS_CACHE_TTL_SECONDS = 300
JWKS_MIN_REFRESH_INTERVAL_SECONDS = 30
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
# Loopback hosts allowed to use http:// for the JWKS URL in local development.
_JWKS_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
T = TypeVar("T")

# Maps raw external claim values to a normalized access level. The level
# vocabulary and the deny-only enforcement live in the authorization package
# (see ``access_ceiling``); this alias table is the auth-side interpretation of
# provider-specific claim strings.
_EXTERNAL_ACCESS_ALIASES = {
    "view": EXTERNAL_ACCESS_VIEWER,
    "viewer": EXTERNAL_ACCESS_VIEWER,
    "read": EXTERNAL_ACCESS_VIEWER,
    "readonly": EXTERNAL_ACCESS_VIEWER,
    "read_only": EXTERNAL_ACCESS_VIEWER,
    "read-only": EXTERNAL_ACCESS_VIEWER,
    "edit": EXTERNAL_ACCESS_EDITOR,
    "editor": EXTERNAL_ACCESS_EDITOR,
    "write": EXTERNAL_ACCESS_EDITOR,
    "developer": EXTERNAL_ACCESS_EDITOR,
    "admin": EXTERNAL_ACCESS_ADMIN,
    "administrator": EXTERNAL_ACCESS_ADMIN,
}


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


def _normalize_access_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _EXTERNAL_ACCESS_ALIASES.get(normalized, normalized if normalized in EXTERNAL_ACCESS_LEVELS else None)


def _access_claim_mapping(auth_settings: AuthSettings) -> dict[str, str]:
    raw_mapping = auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING
    if not raw_mapping:
        return {}

    mapping: dict[str, str] = {}
    try:
        loaded = json.loads(raw_mapping)
    except json.JSONDecodeError:
        loaded = None

    if isinstance(loaded, Mapping):
        pairs = loaded.items()
    else:
        pairs = []
        for item in raw_mapping.split(","):
            key, separator, value = item.partition(":")
            if not separator:
                continue
            pairs.append((key, value))

    for key, value in pairs:
        if not isinstance(key, str):
            continue
        normalized_level = _normalize_access_level(str(value))
        if normalized_level is not None:
            mapping[key.strip().lower()] = normalized_level
    return mapping


def access_context_from_identity(
    identity: ExternalIdentity,
    auth_settings: AuthSettings,
) -> ExternalAccessContext | None:
    """Return the request-local access ceiling for an external identity."""
    if not auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED:
        return None

    claim_name = auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM
    claim_value = _claim_as_str(identity.claims, claim_name)
    mapping = _access_claim_mapping(auth_settings)
    # Gate the alias fallthrough on whether the operator CONFIGURED a mapping
    # (the raw setting), not on whether it parsed to a non-empty dict. A
    # configured-but-all-invalid mapping still parses empty; treating that as
    # "no mapping" would let a raw "admin"/"editor" claim self-elevate via the
    # alias table, re-opening the hole the authoritative-mapping rule closes.
    raw_mapping_configured = bool((auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING or "").strip())
    mapped_level = None
    if claim_value is not None:
        mapped_level = mapping.get(claim_value.strip().lower())
        # When an explicit mapping is configured it is authoritative: a claim
        # value absent from it must NOT be reinterpreted through the built-in
        # alias table (otherwise a raw "admin"/"editor" claim would silently
        # elevate without an explicit grant). Fall through to the default level
        # instead. The alias interpretation is only used when NO mapping is
        # configured at all.
        if mapped_level is None and not raw_mapping_configured:
            mapped_level = _normalize_access_level(claim_value)
    level = mapped_level or _normalize_access_level(auth_settings.EXTERNAL_AUTH_DEFAULT_ACCESS_LEVEL)
    if level is None:
        level = EXTERNAL_ACCESS_VIEWER

    return ExternalAccessContext(
        provider=identity.provider,
        subject=identity.subject,
        level=level,
        claim_name=claim_name,
        claim_value=claim_value,
    )


def _validate_trusted_time_claims(claims: Mapping[str, Any]) -> None:
    now = datetime.now(timezone.utc).timestamp()
    exp = claims.get("exp")
    # A token that omits exp never expires. Require it on the trusted-decode
    # path too so a credential without an expiry is rejected rather than
    # accepted forever (mirrors the JWKS path's require=["exp"]).
    if exp is None:
        msg = "External credential is missing exp"
        raise AuthInvalidTokenError(msg)
    if now > float(exp):
        msg = "External credential has expired"
        raise AuthInvalidTokenError(msg)

    nbf = claims.get("nbf")
    if nbf is not None and now < float(nbf):
        msg = "External credential is not valid yet"
        raise AuthInvalidTokenError(msg)


def _require_https_jwks_url(jwks_url: str) -> None:
    """Reject a non-https JWKS URL (http allowed only for loopback hosts).

    Belt-and-suspenders alongside the settings validator: an http:// JWKS lets a
    network MITM swap the signing keys and forge tokens, so the fetch itself
    refuses anything that is not https (or http to a loopback host for dev).
    """
    parsed = urlparse(jwks_url)
    scheme = parsed.scheme.lower()
    if scheme == "https":
        return
    if scheme == "http" and parsed.hostname in _JWKS_LOOPBACK_HOSTS:
        return
    msg = "External JWKS URL must use https (http is allowed only for localhost)"
    raise AuthInvalidTokenError(msg)


async def _fetch_jwks(jwks_url: str, *, force_refresh: bool = False) -> dict[str, Any]:
    _require_https_jwks_url(jwks_url)
    cached = _jwks_cache.get(jwks_url)
    now = time.monotonic()
    if cached and cached[0] > now:
        # force_refresh is rate-limited so attacker-supplied kids cannot turn
        # every rejected token into a fetch against the IdP's JWKS endpoint.
        fetched_at = cached[0] - JWKS_CACHE_TTL_SECONDS
        if not force_refresh or now - fetched_at < JWKS_MIN_REFRESH_INTERVAL_SECONDS:
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
    Otherwise ``EXTERNAL_AUTH_JWKS_URL`` and ``EXTERNAL_AUTH_AUDIENCE`` are both
    required: the signature is verified against the fetched JWKS using
    ``EXTERNAL_AUTH_ALGORITHMS`` and the ``aud`` claim is bound to this
    deployment so tokens the IdP minted for other services are rejected.
    ``EXTERNAL_AUTH_ISSUER`` is verified when set. ``exp`` is required and
    verified on both paths (a token that omits it is rejected); ``nbf`` is
    verified when present.
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

        audience = _split_csv(auth_settings.EXTERNAL_AUTH_AUDIENCE)
        if not audience:
            # Without audience binding, any token the IdP minted for a *different*
            # relying party would verify here (same signing keys, valid exp).
            # Audience is the control that stops cross-service token reuse, so it
            # is required whenever signatures are checked against a JWKS.
            msg = (
                "External JWKS verification requires EXTERNAL_AUTH_AUDIENCE so tokens the IdP issued "
                "for other services are rejected. Set EXTERNAL_AUTH_AUDIENCE to this deployment's "
                "expected audience, or only enable EXTERNAL_AUTH_TRUSTED_JWT_DECODE behind a proxy "
                "that already validates audience."
            )
            raise AuthInvalidTokenError(msg)

        jwks = await _fetch_jwks(auth_settings.EXTERNAL_AUTH_JWKS_URL)
        try:
            jwk = _select_jwk(jwks, token)
        except AuthInvalidTokenError:
            # The token's kid may belong to a key published after the cached
            # JWKS was fetched (IdP key rotation). Refetch once; when the
            # rate limit suppresses the refetch we get the same cached object
            # back and re-raise the original error.
            refreshed = await _fetch_jwks(auth_settings.EXTERNAL_AUTH_JWKS_URL, force_refresh=True)
            if refreshed is jwks:
                raise
            jwk = _select_jwk(refreshed, token)
        signing_key = jwt.PyJWK.from_dict(jwk).key
        issuer = auth_settings.EXTERNAL_AUTH_ISSUER or None
        algorithms = _split_csv(auth_settings.EXTERNAL_AUTH_ALGORITHMS) or ["RS256"]

        return jwt.decode(
            token,
            signing_key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={
                "verify_aud": True,
                "verify_iss": bool(issuer),
                # PyJWT only rejects an *expired* exp; a token that omits exp
                # otherwise passes and never expires. require=["exp"] forces the
                # claim to be present so unbounded-lifetime tokens are rejected.
                "verify_exp": True,
                "require": ["exp"],
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
