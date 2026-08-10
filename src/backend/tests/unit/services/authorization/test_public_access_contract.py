"""Anonymous direct-link authorization contract (LE-1906)."""

from __future__ import annotations

import importlib

import pytest


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
