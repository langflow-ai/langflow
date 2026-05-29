"""Tests for authorization decorators and route dependencies."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization.actions import FlowAction
from langflow.services.authorization.decorators import requires_flow_permission

from ._common import install_audit_recorder, install_authz, install_settings


@pytest.mark.anyio
async def test_requires_flow_permission_denies_before_body(monkeypatch, fake_user):
    """Decorator runs ensure_flow_permission before the wrapped function."""
    install_settings(monkeypatch, authz_enabled=True)
    from ._common import _StubAuthorizationService

    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    flow_id = uuid4()
    ran = False

    @requires_flow_permission(
        FlowAction.READ, user_param="user", flow_id_param="flow_id", flow_user_id_param="owner_id"
    )
    async def handler(*, user, flow_id, owner_id):  # noqa: ARG001
        nonlocal ran
        ran = True

    with pytest.raises(HTTPException) as exc_info:
        await handler(user=fake_user, flow_id=flow_id, owner_id=uuid4())
    assert exc_info.value.status_code == 403
    assert ran is False


@pytest.mark.anyio
async def test_requires_flow_permission_maps_forbidden_to_value_error(monkeypatch, fake_user):
    """forbidden_as_not_found preserves load_flow's ValueError contract."""
    install_settings(monkeypatch, authz_enabled=True)
    from ._common import _StubAuthorizationService

    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    class _Flow:
        id = uuid4()
        user_id = uuid4()
        workspace_id = None
        folder_id = None
        data = {"nodes": []}

    @requires_flow_permission(
        FlowAction.EXECUTE,
        user_param="user",
        flow_param="flow",
        forbidden_as_not_found=True,
        not_found_template="Flow missing",
    )
    async def handler(*, user, flow):  # noqa: ARG001
        return "ok"

    with pytest.raises(ValueError, match="Flow missing"):
        await handler(user=fake_user, flow=_Flow())


def test_requires_flow_permission_raises_on_missing_user_param():
    """Misconfigured decorators fail at decoration time."""
    with pytest.raises(TypeError, match="must have a 'actor' parameter"):

        @requires_flow_permission(FlowAction.READ, user_param="actor")
        async def bad(*, user):
            pass


def test_requires_flow_permission_raises_on_missing_flow_id_param():
    """Existing-resource actions must not silently authorize flow:*."""
    with pytest.raises(TypeError, match="must have a 'missing_id' parameter"):

        @requires_flow_permission(FlowAction.READ, user_param="user", flow_id_param="missing_id")
        async def bad(*, user, flow_id):
            pass


@pytest.mark.anyio
async def test_requires_flow_permission_rejects_none_flow_id_before_body(fake_user):
    """A None resource id fails closed before ensure_flow_permission can see flow:*."""
    ran = False

    @requires_flow_permission(FlowAction.READ, user_param="user", flow_id_param="flow_id")
    async def handler(*, user, flow_id):  # noqa: ARG001
        nonlocal ran
        ran = True

    with pytest.raises(ValueError, match="non-null 'flow_id'"):
        await handler(user=fake_user, flow_id=None)
    assert ran is False


@pytest.mark.anyio
async def test_requires_flow_permission_resource_param_rejects_missing_id_before_body(fake_user):
    """Loaded-resource mode also fails closed when the row lacks an id."""
    ran = False

    class _Flow:
        id = None
        user_id = uuid4()
        workspace_id = None
        folder_id = None

    @requires_flow_permission(FlowAction.EXECUTE, user_param="user", flow_param="flow")
    async def handler(*, user, flow):  # noqa: ARG001
        nonlocal ran
        ran = True

    with pytest.raises(ValueError, match="non-null 'flow_id'"):
        await handler(user=fake_user, flow=_Flow())
    assert ran is False
