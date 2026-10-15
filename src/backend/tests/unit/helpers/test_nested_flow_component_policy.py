"""Regressions for the caller-aware component policy on the shared nested-flow seam.

H1-3979311 / LE-2543: ``load_flow`` / the ``run_flow`` helper (Sub Flow, Flow as
Tool, internal A2A flow loading, ``CustomComponent.load_flow``) built graphs from
stored flow rows without ``prepare_flow_build_for_user``, so the admin-only
custom-component policy did not propagate across the nested-flow boundary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from lfx.utils.flow_validation import CustomComponentValidationError

CALLER_AUTHORED_SOURCE = "# caller-authored source\nOWN_CODE_RAN = True\n"

CALLER_AUTHORED_COMPONENT = "from lfx.custom import Component\n\n\nclass Probe(Component):\n    pass\n"


def _stored_graph(source: str) -> dict:
    return {
        "nodes": [
            {
                "id": "CustomComponent-1",
                "data": {
                    "id": "CustomComponent-1",
                    "type": "CustomComponent",
                    "node": {"template": {"code": {"value": source}}},
                },
            }
        ],
        "edges": [],
    }


def _child_flow_payload() -> dict:
    """A persistable flow whose component source is the caller's own, matching no registry hash."""
    node_id = "LE2543Probe-1"
    return {
        "name": f"le2543-helper-child-{uuid4().hex[:8]}",
        "description": "regression fixture",
        "data": {
            "nodes": [
                {
                    "id": node_id,
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": node_id,
                        "type": "CustomComponent",
                        "node": {
                            "base_classes": ["Data"],
                            "display_name": "LE2543 Probe",
                            "template": {
                                "_type": "Component",
                                "code": {
                                    "type": "code",
                                    "name": "code",
                                    "value": CALLER_AUTHORED_COMPONENT,
                                    "show": True,
                                },
                            },
                        },
                    },
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


async def test_build_graph_from_authorized_flow_uses_the_sanitized_copy(monkeypatch):
    """The nested graph is built from the policy's trusted copy, not the stored bytes."""
    from langflow.helpers import flow as flow_helpers

    stored = _stored_graph(CALLER_AUTHORED_SOURCE)
    sanitized = {"nodes": [], "edges": []}
    captured: dict = {}

    async def sanitize(target, *, is_superuser):
        captured["target"] = target
        captured["is_superuser"] = is_superuser
        return sanitized

    def fake_from_payload(payload, **_kwargs):
        captured["payload"] = payload
        return SimpleNamespace()

    monkeypatch.setattr("lfx.utils.flow_validation.prepare_flow_build_for_user", sanitize)
    monkeypatch.setattr(flow_helpers, "get_user_is_superuser", AsyncMock(return_value=False))
    monkeypatch.setattr("lfx.graph.graph.base.Graph.from_payload", staticmethod(fake_from_payload))

    flow = SimpleNamespace(data=stored)
    await flow_helpers._build_graph_from_authorized_flow(
        flow=flow,
        flow_id=str(uuid4()),
        user_id=str(uuid4()),
        tweaks=None,
    )

    assert captured["target"] is stored
    assert captured["is_superuser"] is False
    assert captured["payload"] is sanitized
    # The stored row is never rewritten by the sanitizer.
    assert stored["nodes"][0]["data"]["node"]["template"]["code"]["value"] == CALLER_AUTHORED_SOURCE


async def test_build_graph_from_authorized_flow_denial_stops_construction(monkeypatch):
    """A policy rejection on the stored row must abort before any graph is built."""
    from langflow.helpers import flow as flow_helpers

    async def reject(_target, *, is_superuser):
        assert is_superuser is False
        message = "custom components are restricted to administrators"
        raise CustomComponentValidationError(message)

    from_payload = Mock(side_effect=AssertionError("graph must not be built"))
    monkeypatch.setattr("lfx.utils.flow_validation.prepare_flow_build_for_user", reject)
    monkeypatch.setattr(flow_helpers, "get_user_is_superuser", AsyncMock(return_value=False))
    monkeypatch.setattr("lfx.graph.graph.base.Graph.from_payload", staticmethod(from_payload))

    flow = SimpleNamespace(data=_stored_graph(CALLER_AUTHORED_SOURCE))
    with pytest.raises(CustomComponentValidationError, match="restricted to administrators"):
        await flow_helpers._build_graph_from_authorized_flow(
            flow=flow,
            flow_id=str(uuid4()),
            user_id=str(uuid4()),
            tweaks=None,
        )

    from_payload.assert_not_called()


async def test_build_graph_from_authorized_flow_forwards_superuser_status(monkeypatch):
    """A superuser's stored source keeps working; the flag must reach the policy."""
    from langflow.helpers import flow as flow_helpers

    seen: dict = {}

    async def permissive(_target, *, is_superuser):
        seen["is_superuser"] = is_superuser

    monkeypatch.setattr("lfx.utils.flow_validation.prepare_flow_build_for_user", permissive)
    monkeypatch.setattr(flow_helpers, "get_user_is_superuser", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "lfx.graph.graph.base.Graph.from_payload",
        staticmethod(lambda _payload, **_kwargs: SimpleNamespace()),
    )

    flow = SimpleNamespace(data=_stored_graph(CALLER_AUTHORED_SOURCE))
    await flow_helpers._build_graph_from_authorized_flow(
        flow=flow,
        flow_id=str(uuid4()),
        user_id=str(uuid4()),
        tweaks=None,
    )

    assert seen["is_superuser"] is True


async def test_get_user_is_superuser_resolves_the_flag(client, active_user):  # noqa: ARG001
    """The nested seam fails closed: unknown or missing identities are not superusers."""
    from langflow.helpers.flow import get_user_is_superuser
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    assert await get_user_is_superuser(str(active_user.id)) is False

    # Flip the same row: the active_user/active_super_user fixtures share one user,
    # so they cannot be combined in a single test.
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        user.is_superuser = True
        session.add(user)
    try:
        assert await get_user_is_superuser(str(active_user.id)) is True
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.is_superuser = False
            session.add(user)

    assert await get_user_is_superuser(str(uuid4())) is False
    assert await get_user_is_superuser(None) is False
    assert await get_user_is_superuser("not-a-uuid") is False


@pytest.mark.security
async def test_load_flow_denies_regular_user_under_real_admin_only_policy(
    client, active_user, logged_in_headers, monkeypatch
):
    """End-to-end with the REAL policy through the shared ``load_flow`` seam."""
    from langflow.helpers.flow import load_flow
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    created = await client.post("api/v1/flows/", json=_child_flow_payload(), headers=logged_in_headers)
    assert created.status_code == 201
    child_id = created.json()["id"]

    with pytest.raises(CustomComponentValidationError):
        await load_flow(str(active_user.id), flow_id=child_id)

    await client.delete(f"api/v1/flows/{child_id}", headers=logged_in_headers)


@pytest.mark.security
async def test_load_flow_lets_superuser_load_the_same_child(
    client, active_super_user, logged_in_headers_super_user, monkeypatch
):
    """The contrast that makes the denial meaningful: the gate is caller-aware.

    Everything up to graph construction is real (settings, DB rows, the EXECUTE
    check, the policy); only the constructor is stubbed, since this minimal
    fixture payload is not a fully buildable graph.
    """
    from langflow.helpers.flow import load_flow
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    created = await client.post("api/v1/flows/", json=_child_flow_payload(), headers=logged_in_headers_super_user)
    assert created.status_code == 201
    child_id = created.json()["id"]

    captured: dict = {}

    def fake_from_payload(payload, **_kwargs):
        captured["payload"] = payload
        return SimpleNamespace(flow_id=child_id)

    monkeypatch.setattr("lfx.graph.graph.base.Graph.from_payload", staticmethod(fake_from_payload))

    graph = await load_flow(str(active_super_user.id), flow_id=child_id)

    assert graph is not None
    # The superuser's stored source reaches the graph constructor unsanitized.
    nodes = captured["payload"]["nodes"]
    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == CALLER_AUTHORED_COMPONENT

    await client.delete(f"api/v1/flows/{child_id}", headers=logged_in_headers_super_user)
