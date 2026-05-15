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
async def test_enforce_denies_non_superuser_when_enabled():
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    service = LangflowAuthorizationService(settings)
    user_id = uuid4()
    assert not await service.enforce(
        user_id=user_id,
        domain="*",
        obj="flow:abc",
        act="write",
        context={"is_superuser": False},
    )


@pytest.mark.anyio
async def test_enforce_allows_superuser_when_enabled_and_bypass():
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
        context={"is_superuser": True},
    )


@pytest.mark.anyio
async def test_is_enabled_reflects_setting(authz_service):
    assert not await authz_service.is_enabled()
    authz_service.settings_service.auth_settings.AUTHZ_ENABLED = True
    assert await authz_service.is_enabled()
