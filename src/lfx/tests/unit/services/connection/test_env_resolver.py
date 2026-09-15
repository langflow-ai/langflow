from __future__ import annotations

import json
import traceback
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
        with pytest.raises(ConnectionUnresolvedError) as caught:
            await EnvConnectionResolver().resolve(_request())
    finally:
        reset_no_env_fallback(token)
    assert caught.value.details["reason"] == "env-fallback-disabled"
    assert "request" in caught.value.hint
    assert "Set LF_CONNECTION" not in str(caught.value)


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
@pytest.mark.parametrize("field", ["refresh_token", "client_secret", "password"])
async def test_long_lived_secrets_are_rejected(variable_service: VariableService, field: str) -> None:
    variable_service.set_variable(
        _request().ref.env_key(),
        json.dumps({"access_token": "token", field: "must-not-enter-runtime"}),
    )

    with pytest.raises(ConnectionUnresolvedError) as caught:
        await EnvConnectionResolver().resolve(_request())
    assert caught.value.details["reason"] == "long-lived-secret"
    assert "refresh_token" in caught.value.hint
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert "must-not-enter-runtime" not in repr(vars(caught.value))
    assert "must-not-enter-runtime" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("raw", ["token", '{"access_token":"token"}'])
async def test_required_scopes_reject_unverified_credentials(variable_service: VariableService, raw: str) -> None:
    request = _request(scopes=frozenset({"drive.read"}))
    variable_service.set_variable(request.ref.env_key(), raw)
    with pytest.raises(ScopeMissingError) as caught:
        await EnvConnectionResolver().resolve(request)
    assert caught.value.details["scopes_verified"] is False
    assert "scopes" in caught.value.hint


@pytest.mark.parametrize("raw", ["token", '{"access_token":"token"}'])
async def test_unverified_credentials_work_without_required_scopes(variable_service: VariableService, raw: str) -> None:
    variable_service.set_variable(_request().ref.env_key(), raw)
    credential = await EnvConnectionResolver().resolve(_request())
    assert credential.access_token.get_secret_value() == "token"
    assert credential.scopes_verified is False


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


@pytest.mark.parametrize(
    ("invalid_fields", "reason"),
    [
        ({"account": {"id": "ok", "id_token": "sensitive-wire-value"}}, "invalid-account"),
        ({"account": "sensitive-wire-value"}, "invalid-account"),
        ({"expires_at": "sensitive-wire-value"}, "invalid-expiry"),
        ({"expires_at": 1e300}, "invalid-expiry"),
        ({"scopes": {"invalid": "sensitive-wire-value"}}, "invalid-scopes"),
        ({"token_type": ["sensitive-wire-value"]}, "invalid-token-type"),
        ({"sensitive-wire-value": "unknown field name"}, "unsupported-fields"),
        ({"access_token": ""}, "invalid-access-token"),
    ],
)
async def test_malformed_credentials_are_typed_without_raw_exception_context(
    variable_service: VariableService, invalid_fields: dict, reason: str
) -> None:
    payload = {"access_token": "sensitive-wire-value", **invalid_fields}
    variable_service.set_variable(_request().ref.env_key(), json.dumps(payload))

    with pytest.raises(ConnectionUnresolvedError) as caught:
        await EnvConnectionResolver().resolve(_request())

    error = caught.value
    assert error.reason == reason
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "sensitive-wire-value" not in "".join(traceback.format_exception(error))
    assert "sensitive-wire-value" not in repr(vars(error))
    assert error.env_key == _request().ref.env_key()


async def test_malformed_json_is_typed(variable_service: VariableService) -> None:
    variable_service.set_variable(_request().ref.env_key(), '{"access_token":"sensitive-wire-value"')
    with pytest.raises(ConnectionUnresolvedError) as caught:
        await EnvConnectionResolver().resolve(_request())
    assert caught.value.__context__ is None
    assert caught.value.reason == "malformed-json"


@pytest.mark.parametrize("provider", ["google", "google_workspace"])
async def test_resolver_applies_shared_scope_normalization(variable_service: VariableService, provider: str) -> None:
    request = ConnectionResolutionRequest(
        ref=ConnectionRef.parse(f"{provider}/work"),
        principal=ExecutionPrincipal(kind="headless_operator"),
        required_scopes=frozenset({"https://www.googleapis.com/auth/drive.readonly"}),
    )
    variable_service.set_variable(
        request.ref.env_key(), json.dumps({"access_token": "token", "scopes": ["drive.readonly"]})
    )

    assert (await EnvConnectionResolver().resolve(request)).scopes_verified
