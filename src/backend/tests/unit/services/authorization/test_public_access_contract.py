"""Anonymous direct-link authorization contract (LE-1906)."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


def _contract_module():
    return importlib.import_module("langflow.services.authorization.public_access")


def test_public_grants_only_confer_read_and_execute_actions():
    """Even an admin-level PUBLIC row cannot grant anonymous mutation or deployment rights."""
    module = _contract_module()
    action = module.PublicResourceAction

    assert module.public_grant_allows("admin", action.READ)
    assert module.public_grant_allows("admin", action.EXECUTE)
    for forbidden in (action.WRITE, action.CREATE, action.DELETE, action.DEPLOY, action.ADMIN):
        assert not module.public_grant_allows("admin", forbidden)


def test_read_share_does_not_confer_execute_but_execute_share_includes_read():
    module = _contract_module()
    action = module.PublicResourceAction

    assert module.public_grant_allows("read", action.READ)
    assert not module.public_grant_allows("read", action.EXECUTE)
    assert module.public_grant_allows("execute", action.READ)
    assert module.public_grant_allows("execute", action.EXECUTE)


def test_anonymous_execution_user_is_stable_and_non_privileged():
    """The runtime principal is deterministic but is not an owner or a persisted user identity."""
    module = _contract_module()

    first = module.public_execution_user()
    second = module.public_execution_user()
    assert first.id == second.id == module.PUBLIC_ANONYMOUS_ACTOR_ID
    assert first.username == "anonymous-public"
    assert first.is_superuser is False
    assert first.store_api_key is None


@pytest.mark.anyio
@pytest.mark.parametrize("action_name", ["WRITE", "CREATE", "DELETE", "DEPLOY", "ADMIN"])
async def test_compatibility_grants_cannot_bypass_action_floor(action_name):
    """Legacy flags never become an alternate path to anonymous mutations."""
    module = _contract_module()

    source = await module._resolve_grant(
        flow=object(),
        action=getattr(module.PublicResourceAction, action_name),
        session=None,
        compatibility_grant=module.PublicGrantSource.A2A_AUTH_NONE,
    )

    assert source is None


@pytest.mark.anyio
async def test_a2a_compatibility_grant_allows_execute_when_no_public_share():
    module = _contract_module()
    result = SimpleNamespace(first=lambda: None)
    session = SimpleNamespace(exec=AsyncMock(return_value=result))
    flow = SimpleNamespace(id=uuid4(), access_type=object())

    source = await module._resolve_grant(
        flow=flow,
        action=module.PublicResourceAction.EXECUTE,
        session=session,
        compatibility_grant=module.PublicGrantSource.A2A_AUTH_NONE,
    )

    assert source is module.PublicGrantSource.A2A_AUTH_NONE


def _session_with_public_share(permission_level: str | None):
    result = SimpleNamespace(first=lambda: permission_level)
    return SimpleNamespace(exec=AsyncMock(return_value=result))


@pytest.mark.anyio
async def test_canonical_read_share_bounds_a_still_public_legacy_flow():
    """A read-only PUBLIC share is authoritative; the legacy flag cannot widen it to execute."""
    module = _contract_module()
    flow = SimpleNamespace(id=uuid4(), access_type=module.AccessTypeEnum.PUBLIC)

    read_source = await module._resolve_grant(
        flow=flow,
        action=module.PublicResourceAction.READ,
        session=_session_with_public_share("read"),
        compatibility_grant=None,
    )
    execute_source = await module._resolve_grant(
        flow=flow,
        action=module.PublicResourceAction.EXECUTE,
        session=_session_with_public_share("read"),
        compatibility_grant=None,
    )

    assert read_source is module.PublicGrantSource.AUTHZ_SHARE
    assert execute_source is None


@pytest.mark.anyio
async def test_canonical_read_share_also_bounds_the_a2a_compatibility_grant():
    module = _contract_module()
    flow = SimpleNamespace(id=uuid4(), access_type=object())

    source = await module._resolve_grant(
        flow=flow,
        action=module.PublicResourceAction.EXECUTE,
        session=_session_with_public_share("read"),
        compatibility_grant=module.PublicGrantSource.A2A_AUTH_NONE,
    )

    assert source is None


@pytest.mark.anyio
async def test_deleting_the_share_falls_back_to_the_documented_legacy_grant():
    """With no share row the legacy flag is still the compatibility grant it claims to be."""
    module = _contract_module()
    flow = SimpleNamespace(id=uuid4(), access_type=module.AccessTypeEnum.PUBLIC)

    source = await module._resolve_grant(
        flow=flow,
        action=module.PublicResourceAction.EXECUTE,
        session=_session_with_public_share(None),
        compatibility_grant=None,
    )

    assert source is module.PublicGrantSource.LEGACY_ACCESS_TYPE


@pytest.mark.anyio
@pytest.mark.parametrize(
    "plugin_result",
    ["allow", "unsupported", "missing_tenant", "deny", "error", "service_unavailable"],
)
async def test_enabled_authorization_plugin_controls_public_execution(monkeypatch, plugin_result):
    module = _contract_module()
    flow = SimpleNamespace(id=uuid4(), workspace_id=None, folder_id=None)
    service = SimpleNamespace(
        supports_public_principals=AsyncMock(return_value=plugin_result != "unsupported"),
        resolve_public_tenant=AsyncMock(return_value=None if plugin_result == "missing_tenant" else "tenant-a"),
        enforce_public=AsyncMock(return_value=plugin_result == "allow"),
    )
    if plugin_result == "error":
        service.supports_public_principals.side_effect = RuntimeError("plugin detail")

    monkeypatch.setattr(module, "_resolve_grant", AsyncMock(return_value=module.PublicGrantSource.AUTHZ_SHARE))
    settings = SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True))
    monkeypatch.setattr(module, "get_settings_service", lambda: settings)
    if plugin_result == "service_unavailable":
        # A service that cannot even be constructed must deny like any other
        # policy failure, not escape the handler as an unhandled 500.
        def _unavailable():
            msg = "authorization service unavailable"
            raise RuntimeError(msg)

        monkeypatch.setattr(module, "get_authorization_service", _unavailable)
    else:
        monkeypatch.setattr(module, "get_authorization_service", lambda: service)
    audit = AsyncMock()
    monkeypatch.setattr(module, "audit_decision", audit)

    if plugin_result == "allow":
        principal = await module.authorize_public_flow_access(
            flow=flow,
            action=module.PublicResourceAction.EXECUTE,
        )
        assert principal.actor_type == "anonymous_public"
    else:
        with pytest.raises(HTTPException) as exc_info:
            await module.authorize_public_flow_access(
                flow=flow,
                action=module.PublicResourceAction.EXECUTE,
            )
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == module.PUBLIC_FLOW_NOT_FOUND_DETAIL

    audit.assert_awaited_once()
