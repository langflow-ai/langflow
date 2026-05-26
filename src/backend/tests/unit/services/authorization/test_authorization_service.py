from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization.service import LangflowAuthorizationService


@pytest.fixture
def authz_service():
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=False,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    return LangflowAuthorizationService(settings)


@pytest.mark.anyio
async def test_enforce_allows_all_when_disabled(authz_service):
    user_id = uuid4()
    assert await authz_service.enforce(
        user_id=user_id,
        domain="*",
        obj="flow:*",
        act="write",
    )


@pytest.mark.anyio
async def test_enforce_allows_non_superuser_when_enabled():
    """OSS stub does not deny; authorization plugin replaces this service for enforcement."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    service = LangflowAuthorizationService(settings)
    user_id = uuid4()
    assert await service.enforce(
        user_id=user_id,
        domain="*",
        obj="flow:abc",
        act="write",
        context={"is_superuser": False},
    )


@pytest.mark.anyio
async def test_is_enabled_reflects_setting(authz_service):
    assert not await authz_service.is_enabled()
    authz_service.settings_service.auth_settings.AUTHZ_ENABLED = True
    assert await authz_service.is_enabled()


@pytest.mark.anyio
async def test_batch_enforce_all_true_when_disabled(authz_service):
    """When AUTHZ_ENABLED=False, batch_enforce returns True for every request."""
    user_id = uuid4()
    requests = [("flow:a", "read"), ("flow:b", "write"), ("flow:c", "delete")]
    result = await authz_service.batch_enforce(
        user_id=user_id,
        domain="*",
        requests=requests,
    )
    assert result == [True, True, True]


@pytest.mark.anyio
async def test_batch_enforce_allows_non_superuser_when_enabled():
    """OSS pass-through allows every batch request regardless of user context."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    service = LangflowAuthorizationService(settings)
    requests = [("flow:a", "read"), ("flow:b", "write")]
    result = await service.batch_enforce(
        user_id=uuid4(),
        domain="*",
        requests=requests,
        context={"is_superuser": False},
    )
    assert result == [True, True]


@pytest.mark.anyio
async def test_batch_enforce_empty_requests(authz_service):
    """An empty request list returns an empty list."""
    result = await authz_service.batch_enforce(
        user_id=uuid4(),
        domain="*",
        requests=[],
    )
    assert result == []


@pytest.mark.anyio
async def test_get_allowed_actions_returns_all_actions():
    """Pass-through service returns every requested action regardless of user/context."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    service = LangflowAuthorizationService(settings)
    actions = ["read", "write", "delete"]
    result = await service.get_allowed_actions(
        user_id=uuid4(),
        domain="*",
        obj="flow:abc",
        actions=actions,
        context={"is_superuser": False},
    )
    assert result == actions


@pytest.mark.anyio
async def test_get_allowed_actions_returns_all_when_disabled(authz_service):
    """When AUTHZ_ENABLED=False, every requested action is allowed."""
    actions = ["read", "write", "execute"]
    result = await authz_service.get_allowed_actions(
        user_id=uuid4(),
        domain="*",
        obj="flow:any",
        actions=actions,
    )
    assert result == actions
