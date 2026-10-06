from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.api.v1 import endpoints
from langflow.services.auth import utils as auth_utils
from langflow.services.telemetry.context import (
    get_current_telemetry_user_id,
    reset_current_telemetry_user,
    set_current_telemetry_user,
)
from lfx.services.telemetry.identity import get_hashed_user_id


@pytest.fixture(autouse=True)
def reset_telemetry_identity():
    token = set_current_telemetry_user(None)
    try:
        yield
    finally:
        reset_current_telemetry_user(token)


@pytest.mark.asyncio
async def test_optional_user_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(username="alice", is_active=True)
    auth_service = SimpleNamespace(get_current_user=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)

    result = await auth_utils.get_optional_user(None, None, None, db=AsyncMock())

    assert result is user
    assert get_current_telemetry_user_id() == get_hashed_user_id("alice")


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_method", [auth_utils.api_key_security, auth_utils.ws_api_key_security])
async def test_api_key_user_sets_telemetry_identity(monkeypatch, auth_method) -> None:
    user = SimpleNamespace(username="alice")
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
    assert get_current_telemetry_user_id() == get_hashed_user_id("alice")


@pytest.mark.asyncio
async def test_current_user_optional_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(username="alice")
    auth_service = SimpleNamespace(get_current_user_for_sse=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)
    request = SimpleNamespace(cookies={"access_token_lf": "token"}, query_params={}, headers={})

    result = await auth_utils.get_current_user_optional(request, db=AsyncMock())

    assert result is user
    assert get_current_telemetry_user_id() == get_hashed_user_id("alice")


@pytest.mark.asyncio
async def test_webhook_auth_sets_telemetry_identity(monkeypatch) -> None:
    user = SimpleNamespace(id="user-id", username="alice")
    auth_service = SimpleNamespace(get_webhook_user=AsyncMock(return_value=user))
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: auth_service)
    monkeypatch.setattr(endpoints, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=SimpleNamespace()))

    await endpoints.get_webhook_auth("flow-id", SimpleNamespace())

    assert get_current_telemetry_user_id() == get_hashed_user_id("alice")
