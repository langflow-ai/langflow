"""Provider-neutral connection references and short-lived credential leases."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictStr

from lfx.integrations.errors import AuthExpiredError

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.services.authorization.base import ExecutionPrincipal
    from lfx.services.interfaces import ConnectionResolverProtocol


PROVIDER_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"
CONNECTION_NAME_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
_PROVIDER_ID_RE = re.compile(PROVIDER_ID_PATTERN)
_CONNECTION_NAME_RE = re.compile(CONNECTION_NAME_PATTERN)
_ENV_SEPARATOR = "__"
_ENV_PREFIX = "LF_CONNECTION__"
_EXPIRY_MARGIN = timedelta(seconds=60)


def provider_env_segment(provider_id: str) -> str:
    """Return a collision-free environment-key segment for a provider id.

    Alphanumeric characters are uppercased and punctuation is escaped with its
    ASCII hex value.  This keeps the key shell-friendly while preserving the
    distinction between provider ids such as ``a.b``, ``a-b``, and ``a_b``.
    """
    if not _PROVIDER_ID_RE.fullmatch(provider_id):
        msg = f"Invalid integration provider id: {provider_id!r}"
        raise ValueError(msg)
    return "".join(character.upper() if character.isalnum() else f"_{ord(character):02X}" for character in provider_id)


class ConnectionRef(BaseModel):
    """Portable, non-secret reference stored in flow JSON as ``provider/name``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: StrictStr = Field(pattern=PROVIDER_ID_PATTERN, max_length=120)
    name: StrictStr = Field(pattern=CONNECTION_NAME_PATTERN, max_length=64)

    @classmethod
    def parse(cls, value: str | ConnectionRef) -> ConnectionRef:
        """Parse a connection handle, rejecting ambiguous or malformed values."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, str) or value.count("/") != 1:
            msg = "Connection references must use the form '<provider>/<name>'"
            raise ValueError(msg)
        provider, name = value.split("/", 1)
        return cls(provider=provider, name=name)

    def to_handle(self) -> str:
        """Serialize this reference to its stable flow representation."""
        return f"{self.provider}/{self.name}"

    def env_key(self) -> str:
        """Return the environment/request-scope key used by headless runtimes."""
        return f"{_ENV_PREFIX}{provider_env_segment(self.provider)}{_ENV_SEPARATOR}{self.name.upper()}"

    def __str__(self) -> str:
        return self.to_handle()


class ConnectionAccount(BaseModel):
    """Non-secret provider account metadata associated with a credential."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    display: StrictStr | None = None
    tenant_id: StrictStr | None = None


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedCredential:
    """Short-lived credential returned by a host resolver.

    The object refuses pickling so access tokens cannot enter graph snapshots,
    background-job payloads, or process caches by accident.
    """

    access_token: SecretStr
    token_type: str = "Bearer"  # noqa: S105 - OAuth token scheme, not a credential
    expires_at: datetime | None = None
    granted_scopes: frozenset[str] = frozenset()
    scopes_verified: bool = False
    account: ConnectionAccount | None = None
    connection_id: str | None = None
    owner_kind: Literal["user", "instance", "env"] = "env"
    provider: str = ""
    name: str = ""

    def __repr__(self) -> str:
        return (
            "ResolvedCredential(access_token=SecretStr('**********'), "
            f"token_type={self.token_type!r}, expires_at={self.expires_at!r}, "
            f"granted_scopes={self.granted_scopes!r}, scopes_verified={self.scopes_verified!r}, "
            f"account={self.account!r}, connection_id={self.connection_id!r}, "
            f"owner_kind={self.owner_kind!r}, provider={self.provider!r}, name={self.name!r})"
        )

    def __reduce__(self):
        msg = "ResolvedCredential objects cannot be serialized"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class ConnectionResolutionRequest:
    """All non-secret context a host needs to resolve one connection."""

    ref: ConnectionRef
    principal: ExecutionPrincipal
    required_scopes: frozenset[str] = frozenset()
    component_id: str | None = None
    flow_id: str | None = None
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionStatus:
    """Credential-free connection status suitable for pickers and health views."""

    ref: ConnectionRef
    status: Literal["ready", "expired", "missing", "scope_missing", "unavailable"]
    granted_scopes: frozenset[str] = frozenset()
    account: ConnectionAccount | None = None


class CredentialLease:
    """In-process, single-flight lease for a resolver-provided credential."""

    def __init__(
        self,
        resolver: ConnectionResolverProtocol,
        request: ConnectionResolutionRequest,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolver = resolver
        self._request = request
        self._credential: ResolvedCredential | None = None
        self._lock = asyncio.Lock()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._reactive_refresh_completed = False

    @property
    def ref(self) -> ConnectionRef:
        """Return the non-secret reference represented by this lease."""
        return self._request.ref

    @property
    def credential(self) -> ResolvedCredential | None:
        """Return the currently cached credential without resolving it."""
        return self._credential

    def _expires_soon(self, credential: ResolvedCredential) -> bool:
        expires_at = credential.expires_at
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at - self._now() < _EXPIRY_MARGIN

    async def get_credential(self) -> ResolvedCredential:
        """Resolve once, refreshing under one lock when the cached token nears expiry."""
        credential = self._credential
        if credential is not None and not self._expires_soon(credential):
            return credential
        async with self._lock:
            credential = self._credential
            if credential is None or self._expires_soon(credential):
                credential = await self._resolver.resolve(self._request)
                self._credential = credential
            return credential

    async def get_token(self) -> str:
        """Return the access token for immediate use at the provider boundary."""
        credential = await self.get_credential()
        return credential.access_token.get_secret_value()

    async def get_token_after_auth_error(self, error: AuthExpiredError) -> str:
        """Re-resolve once after a provider rejects a no-expiry or stale token."""
        if not isinstance(error, AuthExpiredError):
            msg = "error must be an AuthExpiredError"
            raise TypeError(msg)
        async with self._lock:
            if self._reactive_refresh_completed:
                raise error
            self._reactive_refresh_completed = True
            self._credential = await self._resolver.resolve(self._request)
            credential = self._credential
            return credential.access_token.get_secret_value()
