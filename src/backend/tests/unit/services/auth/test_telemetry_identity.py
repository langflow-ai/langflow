from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1 import endpoints
from langflow.services.auth import utils as auth_utils
from langflow.services.auth.service import AuthService
from langflow.services.telemetry.context import (
    get_current_telemetry_user_id,
    reset_current_telemetry_user,
    set_current_telemetry_user,
)
from lfx.services.telemetry.identity import get_installation_user_id


@pytest.fixture(autouse=True)
def reset_telemetry_identity(monkeypatch):
    monkeypatch.setattr(auth_utils, "get_telemetry_service", lambda: SimpleNamespace(anonymous_id="test-installation"))
    token = set_current_telemetry_user(None)
    try:
        yield
    finally:
        reset_current_telemetry_user(token)


@pytest.mark.asyncio
async def test_optional_user_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(id=uuid4(), username="alice", is_active=True)
    auth_service = SimpleNamespace(get_current_user=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)

    result = await auth_utils.get_optional_user(None, None, None, db=AsyncMock())

    assert result is user
    assert get_current_telemetry_user_id() == get_installation_user_id(user.id, "test-installation")


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_method", [auth_utils.api_key_security, auth_utils.ws_api_key_security])
async def test_api_key_user_sets_telemetry_identity(monkeypatch, auth_method) -> None:
    user = SimpleNamespace(id=uuid4(), username="alice")
    auth_service = SimpleNamespace(
        api_key_security=AsyncMock(return_value=user),
        ws_api_key_security=AsyncMock(return_value=user),
    )
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)

    if auth_method is auth_utils.api_key_security:
        result = await auth_method(None, "api-key")
    else:
        result = await auth_method("api-key")

    assert result is user
    assert get_current_telemetry_user_id() == get_installation_user_id(user.id, "test-installation")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_method", "service_method"),
    [
        (auth_utils.get_current_user_for_websocket, "get_current_user_for_websocket"),
        (auth_utils.get_current_user_for_sse, "get_current_user_for_sse"),
    ],
)
async def test_streaming_user_sets_telemetry_identity(monkeypatch, auth_method, service_method) -> None:
    user = SimpleNamespace(id=uuid4(), username="alice")
    auth_service = SimpleNamespace(**{service_method: AsyncMock(return_value=user)})
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)

    if auth_method is auth_utils.get_current_user_for_websocket:
        request = SimpleNamespace(cookies={}, query_params={}, headers={})
        result = await auth_method(request, AsyncMock())
    else:
        request = SimpleNamespace(cookies={}, query_params={}, headers={})
        result = await auth_method(request, db=AsyncMock())

    assert result is user
    assert get_current_telemetry_user_id() == get_installation_user_id(user.id, "test-installation")


@pytest.mark.asyncio
async def test_current_user_optional_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(id=uuid4(), username="alice")
    auth_service = SimpleNamespace(get_current_user_for_sse=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)
    request = SimpleNamespace(cookies={"access_token_lf": "token"}, query_params={}, headers={})

    result = await auth_utils.get_current_user_optional(request, db=AsyncMock())

    assert result is user
    assert get_current_telemetry_user_id() == get_installation_user_id(user.id, "test-installation")


@pytest.mark.asyncio
async def test_webhook_auth_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(id=uuid4(), username="alice")
    auth_service = SimpleNamespace(get_webhook_user=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)
    monkeypatch.setattr(
        auth_utils,
        "get_settings_service",
        lambda: SimpleNamespace(auth_settings=SimpleNamespace(WEBHOOK_AUTH_ENABLE=True)),
    )
    monkeypatch.setattr(endpoints, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=SimpleNamespace()))

    await endpoints.get_webhook_auth("flow-id", SimpleNamespace())

    assert get_current_telemetry_user_id() == get_installation_user_id(user.id, "test-installation")


@pytest.mark.parametrize("username", [None, "", "langflow"])
def test_default_or_missing_user_uses_installation_fallback(username) -> None:
    auth_utils.set_authenticated_telemetry_user(SimpleNamespace(id=uuid4(), username=username))

    assert get_current_telemetry_user_id() is None


@pytest.mark.asyncio
async def test_public_webhook_does_not_attribute_the_owner(monkeypatch) -> None:
    owner = SimpleNamespace(id="owner-id", username="alice")
    settings = SimpleNamespace(auth_settings=SimpleNamespace(WEBHOOK_AUTH_ENABLE=False))
    auth_service = AuthService(settings)
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)
    monkeypatch.setattr(auth_utils, "get_settings_service", lambda: settings)
    monkeypatch.setattr(
        "langflow.services.auth.service.get_user_by_flow_id_or_endpoint_name",
        AsyncMock(return_value=owner),
    )
    set_current_telemetry_user(uuid4(), "test-installation")

    result = await auth_utils.get_webhook_user("public-flow", SimpleNamespace(headers={}, query_params={}))

    assert result is owner
    assert get_current_telemetry_user_id() is None
