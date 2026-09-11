"""Environment and request-scope resolver for headless lfx runtimes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from lfx.integrations.errors import AuthExpiredError, ConnectionUnresolvedError
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionResolutionRequest,
    ResolvedCredential,
)
from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
from lfx.services.variable.request_scope import is_env_fallback_disabled

if TYPE_CHECKING:
    from lfx.integrations.errors import ConnectionUnresolvedReason


class _InvalidCredentialError(ValueError):
    """Carry only a fixed reason across the private parser boundary."""

    def __init__(self, *, reason: ConnectionUnresolvedReason) -> None:
        self.reason = reason
        super().__init__(reason)


def _parse_expiry(value: Any) -> datetime | None:
    """Interpret optional timestamps as UTC, rejecting invalid wire values."""
    if value is None:
        return None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str):
        msg = "expires_at must be an ISO-8601 string or Unix timestamp"
        raise TypeError(msg)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _parse_wire_value(raw: str, request: ConnectionResolutionRequest) -> ResolvedCredential:
    """Keep raw wire values and validation exceptions out of public error chains."""
    reason: ConnectionUnresolvedReason = "invalid-credential"
    try:
        return _parse_credential(raw, request)
    except _InvalidCredentialError as exc:
        reason = exc.reason
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    # Raise outside the handler so even __context__ cannot retain a raw value.
    raise ConnectionUnresolvedError(
        request.ref.to_handle(), env_key=request.ref.env_key(), provider=request.ref.provider, reason=reason
    )


def _parse_credential(raw: str, request: ConnectionResolutionRequest) -> ResolvedCredential:
    """Validate a token or credential JSON inside the sanitized parser boundary."""
    if not raw:
        raise _InvalidCredentialError(reason="invalid-access-token")
    if not raw.lstrip().startswith("{"):
        return ResolvedCredential(
            access_token=SecretStr(raw),
            provider=request.ref.provider,
            name=request.ref.name,
            owner_kind="env",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise _InvalidCredentialError(reason="malformed-json") from None
    if not isinstance(payload, dict):
        raise _InvalidCredentialError(reason="malformed-json")
    forbidden = {"refresh_token", "client_secret", "password"} & payload.keys()
    if forbidden:
        raise _InvalidCredentialError(reason="long-lived-secret")
    allowed = {"access_token", "token_type", "expires_at", "scopes", "account"}
    unknown = set(payload) - allowed
    if unknown:
        raise _InvalidCredentialError(reason="unsupported-fields")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise _InvalidCredentialError(reason="invalid-access-token")
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list) or any(not isinstance(scope, str) or not scope for scope in scopes):
        raise _InvalidCredentialError(reason="invalid-scopes")
    token_type = payload.get("token_type", "Bearer")
    if not isinstance(token_type, str) or not token_type:
        raise _InvalidCredentialError(reason="invalid-token-type")
    account_payload = payload.get("account")
    try:
        account = ConnectionAccount.model_validate(account_payload) if account_payload is not None else None
    except (ValueError, TypeError):
        raise _InvalidCredentialError(reason="invalid-account") from None
    try:
        expires_at = _parse_expiry(payload.get("expires_at"))
    except (ValueError, TypeError, OverflowError, OSError):
        raise _InvalidCredentialError(reason="invalid-expiry") from None
    return ResolvedCredential(
        access_token=SecretStr(access_token),
        token_type=token_type,
        expires_at=expires_at,
        granted_scopes=frozenset(scopes),
        scopes_verified="scopes" in payload,
        account=account,
        provider=request.ref.provider,
        name=request.ref.name,
        owner_kind="env",
    )


class EnvConnectionResolver(BaseConnectionResolverService):
    """Resolve credentials through the existing variable/request-scope service."""

    def __init__(self) -> None:
        super().__init__()
        self._fallback_variable_service = None
        self.set_ready()

    async def _get_access_policy(self, request: ConnectionResolutionRequest) -> ConnectionAccessPolicy:
        _ = request
        return ConnectionAccessPolicy(owner_kind="env", allow_non_interactive=True)

    async def _resolve(
        self, request: ConnectionResolutionRequest, policy: ConnectionAccessPolicy
    ) -> ResolvedCredential:
        """Resolve and validate the bare-token or JSON headless wire format."""
        _ = policy
        from lfx.services.deps import get_variable_service

        variable_service = get_variable_service()
        if variable_service is None:
            from lfx.services.variable.service import VariableService

            if self._fallback_variable_service is None:
                self._fallback_variable_service = VariableService()
            variable_service = self._fallback_variable_service
        raw = await variable_service.get_variable(request.ref.env_key())
        if raw is None:
            raise ConnectionUnresolvedError(
                request.ref.to_handle(),
                env_key=request.ref.env_key(),
                provider=request.ref.provider,
                reason="env-fallback-disabled" if is_env_fallback_disabled() else "missing",
            )
        credential = _parse_wire_value(str(raw), request)
        if credential.expires_at is not None and credential.expires_at <= datetime.now(timezone.utc):
            raise AuthExpiredError(provider=request.ref.provider)
        return credential

    async def teardown(self) -> None:
        if self._fallback_variable_service is not None:
            await self._fallback_variable_service.teardown()


RequestScopedConnectionResolver = EnvConnectionResolver
