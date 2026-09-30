"""Tests for the OSS cache-invalidation hooks (no-op by default; plugin overrides)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization.service import LangflowAuthorizationService


@pytest.fixture
def authz_service():
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(AUTHZ_ENABLED=False, AUTHZ_SUPERUSER_BYPASS=True),
    )
    return LangflowAuthorizationService(settings)


@pytest.mark.anyio
async def test_invalidate_user_is_noop(authz_service):
    """Default invalidate_user returns None and does not raise."""
    assert await authz_service.invalidate_user(uuid4()) is None


@pytest.mark.anyio
async def test_invalidate_role_is_noop(authz_service):
    """Default invalidate_role returns None and does not raise."""
    assert await authz_service.invalidate_role(uuid4()) is None


@pytest.mark.anyio
async def test_invalidate_all_is_noop(authz_service):
    """Default invalidate_all returns None and does not raise."""
    assert await authz_service.invalidate_all() is None
