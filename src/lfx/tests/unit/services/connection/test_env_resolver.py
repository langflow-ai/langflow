from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from lfx.integrations import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionRef,
    ConnectionResolutionRequest,
    ConnectionUnresolvedError,
    ScopeMissingError,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)
from lfx.services.variable.service import VariableService


def _request(*, scopes: frozenset[str] = frozenset()) -> ConnectionResolutionRequest:
    return ConnectionResolutionRequest(
        ref=ConnectionRef.parse("google/work"),
        principal=ExecutionPrincipal(kind="headless_operator"),
        required_scopes=scopes,
    )


@pytest.fixture
def variable_service(monkeypatch: pytest.MonkeyPatch) -> VariableService:
    service = VariableService()
    monkeypatch.setattr("lfx.services.deps.get_variable_service", lambda: service)
    return service


@pytest.mark.asyncio
async def test_request_scope_beats_environment(
    monkeypatch: pytest.MonkeyPatch,
    variable_service: VariableService,
) -> None:
    _ = variable_service
    env_key = _request().ref.env_key()
    monkeypatch.setenv(env_key, "ambient-token")
    token = activate_request_variables({env_key: "request-token"})
    try:
        credential = await EnvConnectionResolver().resolve(_request())
    finally:
        reset_request_variables(token)

    assert credential.access_token.get_secret_value() == "request-token"


@pytest.mark.asyncio
async def test_no_env_fallback_blocks_ambient_connection(
    monkeypatch: pytest.MonkeyPatch,
    variable_service: VariableService,
) -> None:
    _ = variable_service
    env_key = _request().ref.env_key()
    monkeypatch.setenv(env_key, "ambient-token")
    token = activate_no_env_fallback(disabled=True)
    try:
        with pytest.raises(ConnectionUnresolvedError):
            await EnvConnectionResolver().resolve(_request())
    finally:
        reset_no_env_fallback(token)


@pytest.mark.asyncio
async def test_json_wire_format_and_scopes(variable_service: VariableService) -> None:
    request = _request(scopes=frozenset({"drive.read"}))
    variable_service.set_variable(
        request.ref.env_key(),
        json.dumps(
            {
                "access_token": "short-lived",
                "token_type": "Bearer",
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "scopes": ["drive.read"],
                "account": {"id": "acct-1", "display": "Work"},
            }
        ),
    )

    credential = await EnvConnectionResolver().resolve(request)

    assert credential.scopes_verified is True
    assert credential.account is not None
    assert credential.account.id == "acct-1"


@pytest.mark.asyncio
async def test_missing_and_scope_failures_are_typed(variable_service: VariableService) -> None:
    resolver = EnvConnectionResolver()
    with pytest.raises(ConnectionUnresolvedError):
        await resolver.resolve(_request())

    variable_service.set_variable(_request().ref.env_key(), json.dumps({"access_token": "token", "scopes": []}))
    with pytest.raises(ScopeMissingError):
        await resolver.resolve(_request(scopes=frozenset({"drive.read"})))


@pytest.mark.asyncio
async def test_long_lived_secrets_are_rejected(variable_service: VariableService) -> None:
    variable_service.set_variable(
        _request().ref.env_key(),
        json.dumps({"access_token": "token", "refresh_token": "must-not-enter-runtime"}),
    )

    with pytest.raises(ValueError, match="refresh_token"):
        await EnvConnectionResolver().resolve(_request())


@pytest.mark.asyncio
async def test_expired_credential_is_typed(variable_service: VariableService) -> None:
    variable_service.set_variable(
        _request().ref.env_key(),
        json.dumps(
            {
                "access_token": "expired",
                "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            }
        ),
    )

    with pytest.raises(AuthExpiredError):
        await EnvConnectionResolver().resolve(_request())


@pytest.mark.asyncio
async def test_non_headless_principal_cannot_use_environment_connection(variable_service: VariableService) -> None:
    request = ConnectionResolutionRequest(
        ref=ConnectionRef.parse("google/work"),
        principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
    )
    variable_service.set_variable(request.ref.env_key(), "token")

    with pytest.raises(ConnectionNotAuthorizedError):
        await EnvConnectionResolver().resolve(request)
