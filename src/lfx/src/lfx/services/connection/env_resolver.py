"""Environment and request-scope resolver for headless lfx runtimes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import SecretStr

from lfx.integrations.errors import AuthExpiredError, ConnectionUnresolvedError, ScopeMissingError
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionResolutionRequest,
    ResolvedCredential,
)
from lfx.services.connection.base import BaseConnectionResolverService


def _parse_expiry(value: Any) -> datetime | None:
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
    if not raw:
        raise ConnectionUnresolvedError(
            request.ref.to_handle(), env_key=request.ref.env_key(), provider=request.ref.provider
        )
    if not raw.lstrip().startswith("{"):
        return ResolvedCredential(
            access_token=SecretStr(raw),
            provider=request.ref.provider,
            name=request.ref.name,
            owner_kind="env",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = "Connection credential JSON is malformed"
        raise ValueError(msg) from exc
    if not isinstance(payload, dict):
        msg = "Connection credential JSON must be an object"
        raise TypeError(msg)
    forbidden = {"refresh_token", "client_secret", "password"} & payload.keys()
    if forbidden:
        names = ", ".join(sorted(forbidden))
        msg = f"Connection credential JSON must not contain long-lived secret fields: {names}"
        raise ValueError(msg)
    allowed = {"access_token", "token_type", "expires_at", "scopes", "account"}
    unknown = set(payload) - allowed
    if unknown:
        msg = f"Connection credential JSON contains unsupported fields: {', '.join(sorted(unknown))}"
        raise ValueError(msg)
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        msg = "Connection credential JSON requires a non-empty access_token"
        raise ValueError(msg)
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list) or any(not isinstance(scope, str) or not scope for scope in scopes):
        msg = "Connection credential JSON scopes must be a list of non-empty strings"
        raise ValueError(msg)
    token_type = payload.get("token_type", "Bearer")
    if not isinstance(token_type, str) or not token_type:
        msg = "Connection credential JSON token_type must be a non-empty string"
        raise ValueError(msg)
    account_payload = payload.get("account")
    account = ConnectionAccount.model_validate(account_payload) if account_payload is not None else None
    return ResolvedCredential(
        access_token=SecretStr(access_token),
        token_type=token_type,
        expires_at=_parse_expiry(payload.get("expires_at")),
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

    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        """Resolve and validate the bare-token or JSON headless wire format."""
        denial = self.authorize_principal(
            request,
            connection_owner_id=None,
            owner_kind="env",
            allow_non_interactive=True,
        )
        if denial is not None:
            raise denial

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
                request.ref.to_handle(), env_key=request.ref.env_key(), provider=request.ref.provider
            )
        credential = _parse_wire_value(str(raw), request)
        if credential.expires_at is not None and credential.expires_at <= datetime.now(timezone.utc):
            raise AuthExpiredError(provider=request.ref.provider)
        if credential.scopes_verified:
            missing = request.required_scopes - credential.granted_scopes
            if missing:
                raise ScopeMissingError(frozenset(missing), provider=request.ref.provider)
        return credential

    async def teardown(self) -> None:
        if self._fallback_variable_service is not None:
            await self._fallback_variable_service.teardown()


RequestScopedConnectionResolver = EnvConnectionResolver
