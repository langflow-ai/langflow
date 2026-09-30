"""Tests for authorization service capability flags."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization.service import LangflowAuthorizationService
from lfx.services.authorization import ShareRuleSnapshot
from lfx.services.authorization import base as authz_base
from lfx.services.authorization.base import BaseAuthorizationService
from lfx.services.authorization.service import AuthorizationService as LfxDefaultService


def _settings(*, authz_enabled: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=authz_enabled,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )


@pytest.mark.anyio
async def test_base_class_default_is_false():
    """The class-level constant defaults False so subclasses must opt in."""
    assert BaseAuthorizationService.SUPPORTS_CROSS_USER_FETCH is False
    assert BaseAuthorizationService.SUPPORTS_API_KEY_SCOPES is False


@pytest.mark.anyio
async def test_public_principal_contract_is_explicit_and_defaults_deny():
    """Anonymous authorization is a separate plugin contract, never a fake user allow-all path."""
    principal_type = getattr(authz_base, "AuthorizationPrincipal", None)
    request_type = getattr(authz_base, "PublicAuthorizationRequest", None)
    action_type = getattr(authz_base, "PublicResourceAction", None)

    assert principal_type is not None
    assert request_type is not None
    assert action_type is not None

    first = principal_type.public_anonymous()
    second = principal_type.public_anonymous()
    assert first == second
    assert first.user_id is None
    assert first.actor_type == "anonymous_public"

    request = request_type(
        principal=first,
        resource_type="flow",
        resource_id=uuid4(),
        action=action_type.EXECUTE,
        domain_hint="*",
        request_host="public.example.test",
        grant_source="legacy_access_type",
    )
    service = LfxDefaultService()
    assert await service.supports_public_principals() is False
    assert await service.resolve_public_tenant(request) is None
    assert await service.enforce_public(request, tenant="*") is False


@pytest.mark.anyio
async def test_lfx_default_service_does_not_support_cross_user_fetch():
    """The lfx no-op service inherits the safe default."""
    service = LfxDefaultService()
    assert await service.supports_cross_user_fetch() is False
    assert await service.supports_api_key_scopes() is False


@pytest.mark.anyio
async def test_lfx_default_targeted_share_hooks_are_noops():
    """New hooks stay source-compatible because the framework defaults do nothing."""
    service = LfxDefaultService()
    share_id = uuid4()
    snapshot = ShareRuleSnapshot(
        share_id=share_id,
        resource_type="flow",
        resource_id=uuid4(),
        scope="user",
        target_id=uuid4(),
        permission_level="read",
    )

    assert await service.sync_share(share_id) is None
    assert await service.remove_share_rules(snapshot) is None


def test_share_rule_snapshot_is_framework_neutral_and_immutable():
    snapshot = ShareRuleSnapshot(
        share_id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope="team",
        target_id=uuid4(),
        permission_level="write",
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.permission_level = "read"  # type: ignore[misc]


@pytest.mark.anyio
async def test_langflow_pass_through_does_not_support_cross_user_fetch():
    """OSS pass-through must NOT opt in — that is the strict-pass-through contract."""
    service = LangflowAuthorizationService(_settings())
    assert await service.supports_cross_user_fetch() is False
    assert await service.supports_api_key_scopes() is False


@pytest.mark.anyio
async def test_subclass_can_opt_in():
    """Authorization plugins flip capability constants; the base accepts them."""

    class _Plugin(LangflowAuthorizationService):
        SUPPORTS_CROSS_USER_FETCH = True
        SUPPORTS_API_KEY_SCOPES = True

    service = _Plugin(_settings())
    assert await service.supports_cross_user_fetch() is True
    assert await service.supports_api_key_scopes() is True
