"""Authenticated A2A must enforce the same caller-aware policy as REST runs."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import a2a
from langflow.api.v2 import workflow
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.services.catalog_policy.base import CatalogPolicySnapshot
from lfx.utils import flow_validation as fv


@pytest.fixture
def authenticated_a2a(monkeypatch):
    """Isolate authenticated flow lookup while retaining the real execution gates."""
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    flow = SimpleNamespace(id=uuid4(), user_id=user.id, data=None)
    settings = SimpleNamespace(
        allow_custom_components=True,
        custom_component_admin_only=False,
        block_code_interpreter_components=False,
    )
    catalog = SimpleNamespace(snapshot=CatalogPolicySnapshot())
    trusted = "# trusted server component"
    monkeypatch.setattr(a2a, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=flow))
    monkeypatch.setattr(a2a, "get_user_by_flow_id_or_endpoint_name", AsyncMock(return_value=user))
    monkeypatch.setattr(a2a, "_is_public_a2a_flow", AsyncMock(return_value=False))
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: SimpleNamespace(settings=settings))
    monkeypatch.setattr("lfx.services.deps.get_catalog_policy_service", lambda: catalog)
    monkeypatch.setattr(
        fv, "get_component_hash_lookups_for_validation", lambda: {"ChatInput": {fv._compute_code_hash(trusted)}}
    )
    monkeypatch.setattr(fv, "get_trusted_code_for_validation", lambda _code: trusted)
    execute = AsyncMock(return_value=object())
    monkeypatch.setattr(workflow, "execute_sync_workflow_with_timeout", execute)
    return user, flow, settings, catalog, trusted, execute


def _payload(component_type, source):
    """Create a single code-bearing node for policy validation."""
    return {
        "nodes": [
            {
                "id": "component-1",
                "data": {
                    "id": "component-1",
                    "type": component_type,
                    "node": {"template": {"code": {"value": source}}},
                },
            }
        ],
        "edges": [],
    }


def _restricted_payload(context, policy):
    """Enable one restriction around a payload it must reject."""
    _user, flow, settings, catalog, _trusted, _execute = context
    flow.data = _payload("CustomComponent", "# user supplied component")
    if policy == "admin-only":
        settings.custom_component_admin_only = True
    elif policy == "custom-disabled":
        settings.allow_custom_components = False
    elif policy == "interpreter-disabled":
        settings.block_code_interpreter_components = True
        flow.data = _payload("PythonREPLComponent", "# user supplied component")
    else:
        catalog.snapshot = CatalogPolicySnapshot(blocked_component_keys={"CustomComponent"})
    return flow.data


@pytest.mark.parametrize("policy", ["admin-only", "custom-disabled", "interpreter-disabled", "catalog"])
async def test_authenticated_a2a_rejects_policy_denial_before_executor(authenticated_a2a, policy):
    """Every server restriction stops an authenticated run before execution."""
    user, flow, _settings, _catalog, _trusted, execute = authenticated_a2a
    _restricted_payload(authenticated_a2a, policy)

    with pytest.raises(HTTPException) as exc_info:
        await a2a._run_flow(flow.id, str(uuid4()), "hello", None, admitted_user_id=str(user.id))

    assert exc_info.value.status_code == 400
    execute.assert_not_awaited()


async def test_authenticated_a2a_executes_sanitized_payload(authenticated_a2a):
    """The executor receives a detached trusted graph under the admitted principal."""
    user, flow, settings, _catalog, trusted, execute = authenticated_a2a
    settings.custom_component_admin_only = True
    flow.data = _payload("ChatInput", trusted)
    original = deepcopy(flow.data)

    response = await a2a._run_flow(flow.id, str(uuid4()), "hello", None, admitted_user_id=str(user.id))

    assert response is execute.return_value
    assert execute.await_args.kwargs["parsed"].data == original
    assert execute.await_args.kwargs["parsed"].data is not flow.data
    assert execute.await_args.kwargs["current_user"] is user
    assert flow.data == original


@pytest.mark.parametrize("resume", [False, True])
async def test_authenticated_a2a_cannot_borrow_admin_owner_privileges(authenticated_a2a, resume):
    """A different caller cannot inherit an administrator flow owner's privileges."""
    user, flow, _settings, _catalog, trusted, execute = authenticated_a2a
    user.is_superuser = True
    caller_id = str(uuid4())
    flow.data = _payload("ChatInput", trusted)

    if resume:
        checkpoint = GraphCheckpoint(
            run_id=str(uuid4()), flow_id=str(flow.id), user_id=caller_id, flow_payload=flow.data
        )
        operation = a2a._prepare_a2a_resume_checkpoint(flow.id, checkpoint, admitted_user_id=caller_id)
    else:
        operation = a2a._run_flow(flow.id, str(uuid4()), "hello", None, admitted_user_id=caller_id)
    with pytest.raises(HTTPException) as exc_info:
        await operation

    assert exc_info.value.status_code == 404
    a2a.get_user_by_flow_id_or_endpoint_name.assert_not_awaited()
    execute.assert_not_awaited()


@pytest.mark.parametrize("policy", ["admin-only", "custom-disabled", "interpreter-disabled", "catalog"])
async def test_authenticated_a2a_resume_revalidates_checkpoint(authenticated_a2a, policy):
    """Current server restrictions apply to the stored checkpoint before restoration."""
    user, flow, _settings, _catalog, _trusted, _execute = authenticated_a2a
    payload = _restricted_payload(authenticated_a2a, policy)
    checkpoint = GraphCheckpoint(run_id=str(uuid4()), flow_id=str(flow.id), user_id=str(user.id), flow_payload=payload)

    with pytest.raises(fv.CustomComponentValidationError):
        await a2a._prepare_a2a_resume_checkpoint(flow.id, checkpoint, admitted_user_id=str(user.id))


async def test_authenticated_a2a_resume_preserves_trusted_detached_payload(authenticated_a2a):
    """Resumption sanitizes a detached checkpoint without rewriting persisted source."""
    user, flow, settings, _catalog, trusted, _execute = authenticated_a2a
    settings.custom_component_admin_only = True
    checkpoint = GraphCheckpoint(
        run_id=str(uuid4()),
        flow_id=str(flow.id),
        user_id=str(user.id),
        flow_payload=_payload("ChatInput", trusted),
    )

    prepared, prepared_flow, prepared_user = await a2a._prepare_a2a_resume_checkpoint(
        flow.id, checkpoint, admitted_user_id=str(user.id)
    )

    assert prepared.flow_payload == checkpoint.flow_payload
    assert prepared is not checkpoint
    assert prepared.flow_payload is not checkpoint.flow_payload
    assert prepared_flow is flow
    assert prepared_user is user
