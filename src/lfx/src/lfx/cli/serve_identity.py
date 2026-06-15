"""Per-user identity forwarding for ``lfx serve``.

 This module lets ``lfx serve`` *consume* an upstream identity and thread it
 into flow execution as ``user_id``.

Two modes carry identity, plus an off switch:

``off``
    Default. No identity is read; ``user_id`` stays ``None`` and behavior is
    byte-for-byte identical to a server without this module.

``jwt``
    A signed JWT (``Authorization: Bearer`` or a configured header) is verified
    against the issuer's JWKS before its identity claim is trusted. Missing or
    invalid tokens are rejected with 401. This is the recommended secure mode
    when identity forwarding is enabled (note: ``off`` is the actual default).

``header``
    A plain gateway header (e.g. ``X-Consumer-Username``) is trusted verbatim.
    This is the *weaker* mode — its safety rests entirely on network topology
    (the gateway being the only reachable caller), so it logs a loud startup
    warning naming that assumption. It exists because Kong OSS key-auth callers
    have no JWT.

The verifier owns a small, per-process, TTL'd JWKS cache. It is prefetched at
startup so the first request never pays the fetch round-trip, and JWKS fetch
failures degrade the *request* (401), never the server.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.error import URLError

import jwt
from fastapi import HTTPException

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

IdentityMode = Literal["off", "jwt", "header"]

# Only asymmetric signatures. Pinning these kills the two classic JWT forgeries:
# ``alg: none`` (no signature) and HMAC alg-confusion (signing with the public
# key as an HMAC secret). HS256/384/512 and none are rejected before any crypto.
ALLOWED_ALGORITHMS: tuple[str, ...] = ("RS256", "ES256")

# JWKS cache TTL and the minimum spacing between forced refreshes triggered by an
# unknown ``kid``. The TTL keeps keys fresh through rotation; the refresh floor
# stops a caller spamming bogus ``kid``s from hammering the issuer's JWKS endpoint.
_JWKS_TTL_SECONDS = 3600.0
_JWKS_MIN_REFRESH_INTERVAL_SECONDS = 10.0

_HTTP_TIMEOUT_SECONDS = 10.0

# Env var names used to round-trip identity config into uvicorn worker processes
# (same mechanism as ``LFX_SERVE_NO_ENV_FALLBACK``).
ENV_MODE = "LFX_SERVE_IDENTITY_MODE"
ENV_JWT_ISSUER = "LFX_SERVE_IDENTITY_JWT_ISSUER"
ENV_JWT_AUDIENCE = "LFX_SERVE_IDENTITY_JWT_AUDIENCE"
ENV_JWT_JWKS_URL = "LFX_SERVE_IDENTITY_JWT_JWKS_URL"
ENV_CLAIM = "LFX_SERVE_IDENTITY_CLAIM"
ENV_JWT_HEADER = "LFX_SERVE_IDENTITY_JWT_HEADER"
ENV_TRUSTED_HEADER = "LFX_SERVE_IDENTITY_HEADER"

# Every identity env key — used by the parent to clean up after uvicorn.run().
IDENTITY_ENV_KEYS: tuple[str, ...] = (
    ENV_MODE,
    ENV_JWT_ISSUER,
    ENV_JWT_AUDIENCE,
    ENV_JWT_JWKS_URL,
    ENV_CLAIM,
    ENV_JWT_HEADER,
    ENV_TRUSTED_HEADER,
)


class IdentityConfigError(ValueError):
    """Raised when identity options are incomplete or inconsistent."""


def _fetch_json(url: str) -> dict:
    """Fetch and parse a JSON document over http(s).

    Only http/https URLs are allowed — the scheme guard satisfies the URL-audit
    linter and prevents ``file://``/``ftp://`` smuggling via a misconfigured
    issuer or JWKS URL.
    """
    if not url.lower().startswith(("http://", "https://")):
        msg = f"Refusing to fetch non-http(s) URL: {url!r}"
        raise IdentityConfigError(msg)
    with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 - scheme checked above
        return json.loads(resp.read())


@dataclass(frozen=True)
class IdentityConfig:
    """Immutable identity-layer configuration resolved at serve startup."""

    mode: IdentityMode = "off"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_jwks_url: str | None = None
    claim: str = "sub"
    # Header the JWT is read from in ``jwt`` mode (Bearer prefix stripped if present).
    jwt_header: str = "Authorization"
    # Header trusted verbatim in ``header`` mode.
    trusted_header: str = "X-Consumer-Username"

    def __post_init__(self) -> None:
        if self.mode not in ("off", "jwt", "header"):
            msg = f"Unknown identity mode {self.mode!r}; expected off, jwt, or header."
            raise IdentityConfigError(msg)
        if self.mode == "jwt":
            if not self.jwt_issuer:
                msg = "--identity-jwt-issuer is required when --identity-mode=jwt."
                raise IdentityConfigError(msg)
            if not self.jwt_audience:
                msg = "--identity-jwt-audience is required when --identity-mode=jwt."
                raise IdentityConfigError(msg)
            if not self.claim:
                msg = "--identity-claim must be non-empty when --identity-mode=jwt."
                raise IdentityConfigError(msg)
            # Validate the JWKS URL scheme offline so a typo (e.g. file://) fails
            # at startup rather than masquerading as a transient fetch error later.
            # (A None jwks_url is fine — it's resolved via OIDC discovery from iss.)
            if self.jwt_jwks_url and not self.jwt_jwks_url.lower().startswith(("http://", "https://")):
                msg = f"--identity-jwt-jwks-url must be an http(s) URL, got {self.jwt_jwks_url!r}."
                raise IdentityConfigError(msg)
        if self.mode == "header" and not self.trusted_header:
            msg = "--identity-header must be non-empty when --identity-mode=header."
            raise IdentityConfigError(msg)

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    def to_env(self) -> dict[str, str]:
        """Serialize to env vars for the uvicorn worker round-trip.

        Only ``off`` emits a lone mode key; richer modes emit their settings so a
        worker's :meth:`from_env` reconstructs an identical config.
        """
        env = {ENV_MODE: self.mode}
        if self.mode == "off":
            return env
        if self.jwt_issuer:
            env[ENV_JWT_ISSUER] = self.jwt_issuer
        if self.jwt_audience:
            env[ENV_JWT_AUDIENCE] = self.jwt_audience
        if self.jwt_jwks_url:
            env[ENV_JWT_JWKS_URL] = self.jwt_jwks_url
        env[ENV_CLAIM] = self.claim
        env[ENV_JWT_HEADER] = self.jwt_header
        env[ENV_TRUSTED_HEADER] = self.trusted_header
        return env

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> IdentityConfig:
        """Reconstruct config from worker env vars; absence ⇒ ``off``."""
        mode = environ.get(ENV_MODE, "off")
        if mode == "off":
            return cls(mode="off")
        defaults = cls()
        return cls(
            mode=mode,  # type: ignore[arg-type]
            jwt_issuer=environ.get(ENV_JWT_ISSUER),
            jwt_audience=environ.get(ENV_JWT_AUDIENCE),
            jwt_jwks_url=environ.get(ENV_JWT_JWKS_URL),
            claim=environ.get(ENV_CLAIM, defaults.claim),
            jwt_header=environ.get(ENV_JWT_HEADER, defaults.jwt_header),
            trusted_header=environ.get(ENV_TRUSTED_HEADER, defaults.trusted_header),
        )


class _SigningKeyUnavailableError(Exception):
    """Internal: no signing key for the presented ``kid`` (after a bounded refresh)."""


@dataclass
class _JwksCache:
    """A per-process, TTL'd cache of the issuer's signing keys.

    Holds a parsed ``PyJWKSet``. Refreshes on TTL expiry and, at most once per
    cooldown window, when a request presents an unknown ``kid`` (key rotation).
    Fetch failures keep the existing keys and surface as a per-request error.

    The stale/cold-cache and unknown-``kid`` fetch paths have independent
    cooldown floors (``_last_stale_fetch_at`` / ``_last_unknown_refresh_at``),
    each allowing one fetch per ``min_refresh_interval`` — so the worst case is
    ~two fetches per window, not one, which still bounds a JWKS outage away from
    a per-request fetch storm. The floors are best-effort and lock-free: under
    concurrent requests two threads can both decide to fetch, so the cap is
    approximate, not exact (a redundant fetch is harmless; a lock around the
    blocking fetch would be worse).
    """

    fetch_jwks: Callable[[], dict]
    ttl_seconds: float = _JWKS_TTL_SECONDS
    min_refresh_interval: float = _JWKS_MIN_REFRESH_INTERVAL_SECONDS
    source_label: str = "the JWKS endpoint"  # human-readable source for log messages
    _jwk_set: jwt.PyJWKSet | None = field(default=None, init=False)
    _fetched_at: float | None = field(default=None, init=False)
    _last_stale_fetch_at: float | None = field(default=None, init=False)
    _last_unknown_refresh_at: float | None = field(default=None, init=False)

    def _fetch_into_cache(self) -> None:
        """Best-effort refresh. On failure, keep the existing keys and log loudly.

        A permanent configuration error (bad/undiscoverable JWKS source) is logged
        distinctly from a transient transport/parse failure, so the operator isn't
        told to wait for a recovery that can never come. Either way the cache is
        left intact and requests fail closed (401); serving never aborts here.
        Unexpected exceptions are intentionally NOT swallowed — they surface as a
        real error rather than a silent "keeping cached keys" line.
        """
        try:
            data = self.fetch_jwks()
            self._jwk_set = jwt.PyJWKSet.from_dict(data)
            self._fetched_at = time.monotonic()
        except IdentityConfigError as exc:
            logger.error(
                f"JWKS source is misconfigured ({self.source_label}): {exc} "
                "This is a configuration error, not a transient outage — requests will be "
                "rejected (401) until it is fixed."
            )
        except (URLError, OSError, TimeoutError, json.JSONDecodeError, jwt.PyJWTError) as exc:
            logger.error(
                f"JWKS refresh from {self.source_label} failed ({type(exc).__name__}: {exc}); keeping cached keys."
            )

    def prefetch(self) -> bool:
        """Warm the cache at startup. Logs an error if it stays empty, never raises.

        Returns ``True`` if the cache holds keys after the attempt, ``False`` if it
        stayed empty, so callers can surface a startup warning on a guaranteed channel.
        """
        self._fetch_into_cache()
        if self._jwk_set is None:
            logger.error(
                "JWKS prefetch failed; serving will start but JWT verification will reject requests "
                "(401) until the JWKS endpoint recovers."
            )
            return False
        return True

    def _lookup(self, kid: str) -> jwt.PyJWK | None:
        if self._jwk_set is None:
            return None
        for key in self._jwk_set.keys:
            if key.key_id == kid:
                return key
        return None

    def get_signing_key(self, kid: str) -> jwt.PyJWK:
        now = time.monotonic()
        # Stale/cold cache: refresh, but at most once per cooldown so a down issuer
        # cannot make every request pay its own blocking fetch. The floor is NOT
        # primed by prefetch(), so the first request after a failed prefetch still
        # refetches immediately and recovers.
        fetched_this_call = False
        stale = self._jwk_set is None or (self._fetched_at is not None and now - self._fetched_at > self.ttl_seconds)
        if stale and (
            self._last_stale_fetch_at is None or (now - self._last_stale_fetch_at) >= self.min_refresh_interval
        ):
            self._last_stale_fetch_at = now
            self._fetch_into_cache()
            fetched_this_call = True

        key = self._lookup(kid)
        if key is not None:
            return key

        # Unknown kid (key rotation): refresh at most once per cooldown window (DoS floor).
        # Skip if we already refetched above this call — it would hit the same endpoint.
        if not fetched_this_call and (
            self._last_unknown_refresh_at is None or (now - self._last_unknown_refresh_at) >= self.min_refresh_interval
        ):
            self._last_unknown_refresh_at = now
            self._fetch_into_cache()
            key = self._lookup(kid)

        if key is None:
            raise _SigningKeyUnavailableError(kid)
        return key


class IdentityVerifier:
    """Resolves a verified ``user_id`` from request headers per :class:`IdentityConfig`."""

    _ALLOWED_ALGS: ClassVar[frozenset[str]] = frozenset(ALLOWED_ALGORITHMS)

    def __init__(
        self,
        config: IdentityConfig,
        *,
        jwks_fetcher: Callable[[str], dict] | None = None,
        openid_fetcher: Callable[[str], dict] | None = None,
    ) -> None:
        self._config = config
        self._json_fetch = jwks_fetcher or _fetch_json
        self._openid_fetch = openid_fetcher or jwks_fetcher or _fetch_json
        self._resolved_jwks_url: str | None = config.jwt_jwks_url
        self._jwks: _JwksCache | None = None
        if config.mode == "jwt":
            source_label = config.jwt_jwks_url or f"OIDC discovery from {config.jwt_issuer}"
            self._jwks = _JwksCache(fetch_jwks=self._fetch_signing_jwks, source_label=source_label)

    @property
    def config(self) -> IdentityConfig:
        return self._config

    # -- startup -----------------------------------------------------------

    def prefetch(self) -> bool:
        """In ``jwt`` mode, warm the JWKS cache; otherwise a no-op.

        Returns ``True`` when the cache is warm (or there is nothing to warm, as in
        ``header`` mode), ``False`` when a ``jwt``-mode prefetch left the cache empty.
        """
        if self._jwks is not None:
            return self._jwks.prefetch()
        return True

    def _resolve_jwks_url(self) -> str:
        if self._resolved_jwks_url:
            return self._resolved_jwks_url
        if not self._config.jwt_issuer:
            msg = "Cannot resolve JWKS URL without an issuer."
            raise IdentityConfigError(msg)
        discovery_url = self._config.jwt_issuer.rstrip("/") + "/.well-known/openid-configuration"
        document = self._openid_fetch(discovery_url)
        jwks_uri = document.get("jwks_uri")
        if not jwks_uri:
            msg = f"OIDC discovery at {discovery_url} did not return a jwks_uri."
            raise IdentityConfigError(msg)
        self._resolved_jwks_url = jwks_uri
        return jwks_uri

    def _fetch_signing_jwks(self) -> dict:
        return self._json_fetch(self._resolve_jwks_url())

    # -- per-request -------------------------------------------------------

    def authenticate(self, headers: Mapping[str, str]) -> str | None:
        """Return the caller's identity, or raise ``HTTPException(401)``.

        ``off`` mode returns ``None`` (no identity); the caller treats that as
        "no per-user attribution", preserving the pre-identity behavior.
        """
        if self._config.mode == "off":
            return None
        if self._config.mode == "header":
            return self._authenticate_header(headers)
        return self._authenticate_jwt(headers)

    def _authenticate_header(self, headers: Mapping[str, str]) -> str:
        value = headers.get(self._config.trusted_header)
        if not value or not value.strip():
            raise HTTPException(status_code=401, detail="Missing identity header")
        return value.strip()

    def _extract_token(self, headers: Mapping[str, str]) -> str | None:
        raw = headers.get(self._config.jwt_header)
        if not raw:
            return None
        raw = raw.strip()
        if raw.lower().startswith("bearer "):
            return raw[len("bearer ") :].strip()
        return raw

    def _authenticate_jwt(self, headers: Mapping[str, str]) -> str:
        token = self._extract_token(headers)
        if not token:
            raise HTTPException(status_code=401, detail="Missing identity token")

        # Inspect the unverified header FIRST so alg-confusion and ``alg: none``
        # are rejected before any key resolution or crypto runs.
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Malformed identity token") from exc

        algorithm = unverified_header.get("alg")
        if algorithm not in self._ALLOWED_ALGS:
            raise HTTPException(status_code=401, detail="Unsupported token algorithm")
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token missing key id")

        if self._jwks is None:  # pragma: no cover - constructed for jwt mode
            raise HTTPException(status_code=401, detail="Identity verification unavailable")
        try:
            signing_key = self._jwks.get_signing_key(kid)
        except _SigningKeyUnavailableError as exc:
            raise HTTPException(status_code=401, detail="Unknown token signing key") from exc

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self._config.jwt_audience,
                issuer=self._config.jwt_issuer,
                leeway=60,
                options={"require": ["exp"], "verify_aud": True, "verify_iss": True},
            )
        except jwt.PyJWTError as exc:
            # Static detail only — never echo the token or signature material.
            raise HTTPException(status_code=401, detail="Invalid identity token") from exc

        identity = claims.get(self._config.claim)
        if identity is None or identity == "":
            raise HTTPException(status_code=401, detail=f"Token missing claim '{self._config.claim}'")
        return str(identity)


def build_identity_verifier(config: IdentityConfig) -> IdentityVerifier | None:
    """Construct a verifier for an enabled config, or ``None`` for ``off`` mode."""
    if not config.enabled:
        return None
    return IdentityVerifier(config)
