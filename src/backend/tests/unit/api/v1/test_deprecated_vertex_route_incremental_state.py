"""LE-2356 follow-up: the policy must not destroy the seam's incremental state.

``POST /build/{flow_id}/vertices/{vertex_id}`` is called once per vertex and carries
built state in the flow's graph cache between requests, so a downstream vertex can
read what its upstream produced. The admin-only policy fix rebuilt the graph whenever
``prepare_flow_build_for_user`` returned a sanitized copy -- which is *every* request
from a non-superuser while the policy is on, not only the first. Each call therefore
overwrote the cache entry holding the previous vertex's result, and the second vertex
reported its upstream as unbuilt.

Reported by QA against the PR head: same flow, same server, admin propagates and
non-admin loses the state; with the policy off the non-admin propagates too. The
trigger is exactly admin-only + non-superuser.

The rebuild is still required once, because a graph compiled while the policy was off
embeds the caller's own component source. What was missing is a record of WHICH policy
generation compiled the cached graph, so the rebuild happens once instead of per call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

MARKER = "MARCADOR-123"


async def _trusted_two_node_flow() -> dict:
    """A ChatInput -> ChatOutput flow whose code is the server's own.

    Taking the source from the live registry is what makes the admin-only policy
    APPROVE this flow rather than reject it, so the test exercises the allowed path
    the report is about.
    """
    from langflow.services.deps import get_settings_service
    from lfx.interface.components import get_and_cache_all_types_dict

    all_types = await get_and_cache_all_types_dict(get_settings_service())

    def template_for(component_type: str) -> dict:
        for category in all_types.values():
            if isinstance(category, dict) and component_type in category:
                import json

                return json.loads(json.dumps(category[component_type]))
        msg = f"{component_type} missing from the component registry"
        raise RuntimeError(msg)

    chat_input = template_for("ChatInput")
    chat_output = template_for("ChatOutput")
    source_id, target_id = "ChatInput-le2356", "ChatOutput-le2356"

    return {
        "name": "le2356 incremental",
        "description": "regression fixture",
        "data": {
            "nodes": [
                {
                    "id": source_id,
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {"id": source_id, "type": "ChatInput", "node": chat_input},
                },
                {
                    "id": target_id,
                    "type": "genericNode",
                    "position": {"x": 400, "y": 0},
                    "data": {"id": target_id, "type": "ChatOutput", "node": chat_output},
                },
            ],
            "edges": [
                {
                    "id": "le2356-edge",
                    "source": source_id,
                    "target": target_id,
                    "sourceHandle": (
                        "{œdataTypeœ:œChatInputœ,œidœ:œ" + source_id + "œ,œnameœ:œmessageœ,œoutput_typesœ:[œMessageœ]}"
                    ),
                    "targetHandle": (
                        "{œfieldNameœ:œinput_valueœ,œidœ:œ" + target_id + "œ,œinputTypesœ:[œMessageœ],œtypeœ:œstrœ}"
                    ),
                    "data": {
                        "sourceHandle": {
                            "dataType": "ChatInput",
                            "id": source_id,
                            "name": "message",
                            "output_types": ["Message"],
                        },
                        "targetHandle": {
                            "fieldName": "input_value",
                            "id": target_id,
                            "inputTypes": ["Message"],
                            "type": "str",
                        },
                    },
                }
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


async def _build_chain(client: AsyncClient, headers: dict[str, str]) -> dict:
    """Build the upstream vertex, then the downstream one, as the editor would."""
    created = await client.post("api/v1/flows/", json=await _trusted_two_node_flow(), headers=headers)
    assert created.status_code == 201
    flow_id = created.json()["id"]

    upstream = await client.post(
        f"api/v1/build/{flow_id}/vertices/ChatInput-le2356",
        json={"inputs": {"input_value": MARKER}},
        headers=headers,
    )
    downstream = await client.post(f"api/v1/build/{flow_id}/vertices/ChatOutput-le2356", headers=headers)

    await client.delete(f"api/v1/flows/{flow_id}", headers=headers)
    return {"upstream": upstream, "downstream": downstream}


@pytest.mark.security
async def test_a_permitted_non_admin_keeps_state_between_vertex_builds(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """The policy approves this flow, so the seam must behave as it does without it."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    result = await _build_chain(client, logged_in_headers)

    assert result["upstream"].status_code == 200
    assert MARKER in result["upstream"].text, "the upstream vertex never ran"

    downstream = result["downstream"]
    assert downstream.status_code == 200
    body = downstream.json()
    assert body["valid"] is True, f"downstream lost its upstream state: {str(body.get('params'))[:160]}"
    assert "has not been built yet" not in str(body.get("params", ""))


@pytest.mark.security
async def test_a_superuser_keeps_state_between_vertex_builds(
    client: AsyncClient,
    logged_in_headers_super_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """The control: an admin is exempt from the policy, so this path never regressed.

    Its value is telling a real regression apart from a broken fixture -- if BOTH
    principals fail, the flow itself is wrong, not the policy branch.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    result = await _build_chain(client, logged_in_headers_super_user)

    assert result["downstream"].status_code == 200
    assert result["downstream"].json()["valid"] is True


@pytest.mark.security
async def test_a_non_admin_keeps_state_with_the_policy_off(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """The counter-proof: with the policy off the same caller propagates."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", False)
    monkeypatch.setattr(settings, "allow_custom_components", True)

    result = await _build_chain(client, logged_in_headers)

    assert result["downstream"].status_code == 200
    assert result["downstream"].json()["valid"] is True
