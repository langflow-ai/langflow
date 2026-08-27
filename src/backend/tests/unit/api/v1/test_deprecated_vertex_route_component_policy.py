"""LE-2356: the single-vertex build seam must run the caller-aware component policy.

``POST /api/v1/build/{flow_id}/vertices/{vertex_id}`` compiled the graph persisted on
the flow row and executed one vertex from it. The stored graph is caller-controlled --
any user who can write a flow can persist Python through the ordinary flow API -- and
this seam applied only the caller-agnostic global validator. So with
``custom_component_admin_only`` on, a non-admin was refused on
``/run/{id}``, ``/build/{id}/flow`` and ``/v2/workflows`` yet executed their own source
here.

Reproduced over real HTTP as two real principals before the fix: ``build/{id}/flow``
answered ``400`` for the non-admin while ``build/{id}/vertices/{vid}`` answered ``200``
and returned the marker from their own class.

The policy substitutes the server's trusted source rather than blanket-refusing, so the
control that a permissive policy still builds matters as much as the denial: a refusal
for everyone would be a denial of service wearing a security fix's clothes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

def _vertex_route(flow_id: str, vertex_id: str) -> str:
    return f"api/v1/build/{flow_id}/vertices/{vertex_id}"


@pytest.mark.security
async def test_should_refuse_when_the_caller_aware_policy_rejects_the_stored_graph(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """A policy rejection must surface as 400 and never reach a graph constructor."""
    from langflow.api.v1 import chat as chat_module
    from lfx.utils.flow_validation import CustomComponentValidationError

    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]
    seen: dict = {}

    async def reject(data, *, is_superuser):
        seen["data"] = data
        seen["is_superuser"] = is_superuser
        message = "custom components are not allowed"
        raise CustomComponentValidationError(message)

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", reject)
    build_spy = MagicMock(side_effect=AssertionError("graph must not be built after a policy denial"))
    monkeypatch.setattr(chat_module, "build_graph_from_db", build_spy)

    response = await client.post(_vertex_route(flow_id, vertex_id), headers=logged_in_headers)

    assert response.status_code == 400
    assert "custom components are not allowed" in response.json()["detail"]
    assert seen["data"] == added_flow_webhook_test["data"], "the policy must see the STORED graph"
    build_spy.assert_not_called()


@pytest.mark.security
async def test_should_run_the_policy_with_the_callers_own_privilege(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """The gate is caller-aware: it must be told who is asking, not assume a principal."""
    from langflow.api.v1 import chat as chat_module

    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]
    calls: list[dict] = []

    async def record(_data, *, is_superuser):
        calls.append({"is_superuser": is_superuser})

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", record)

    await client.post(_vertex_route(flow_id, vertex_id), headers=logged_in_headers)

    assert calls, "the seam never consulted the caller-aware policy"
    assert isinstance(calls[0]["is_superuser"], bool)


@pytest.mark.security
async def test_should_build_from_the_sanitized_copy_not_the_stored_bytes(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """When the policy substitutes trusted source, that copy is what must be compiled.

    Rebuilding is required even on a cache hit: cache keys carry no policy generation,
    so a graph compiled while the policy was off still embeds the caller's own source.
    """
    from langflow.api.v1 import chat as chat_module

    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]
    sanitized = {"nodes": [{"id": vertex_id, "data": {"id": vertex_id, "type": "ChatInput"}}], "edges": []}

    async def substitute(_data, *, is_superuser):  # noqa: ARG001
        return sanitized

    built_from: dict = {}

    async def fake_build(*, flow_id, chat_service, graph_data):  # noqa: ARG001
        built_from["graph_data"] = graph_data
        graph = MagicMock()
        graph.set_run_id = MagicMock()
        graph.initialize_run = AsyncMock()
        return graph

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", substitute)
    monkeypatch.setattr(chat_module, "build_and_cache_graph_from_data", fake_build)

    await client.post(_vertex_route(flow_id, vertex_id), headers=logged_in_headers)

    assert built_from.get("graph_data") is sanitized, "the seam compiled the stored bytes, not the trusted copy"


@pytest.mark.security
@pytest.mark.parametrize("failure", ["identity_unavailable", "settings_unavailable"])
async def test_should_fail_closed_when_the_policy_cannot_be_evaluated(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
):
    """An undecidable policy must refuse with 503, never fall through to execution."""
    from langflow.api.v1 import chat as chat_module
    from lfx.utils.flow_validation import CatalogPolicyIdentityUnavailableError

    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]
    error = (
        CatalogPolicyIdentityUnavailableError("identity unavailable")
        if failure == "identity_unavailable"
        else RuntimeError("settings service required")
    )

    async def blow_up(_data, *, is_superuser):  # noqa: ARG001
        raise error

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", blow_up)
    build_spy = MagicMock(side_effect=AssertionError("graph must not be built when the policy is undecidable"))
    monkeypatch.setattr(chat_module, "build_graph_from_db", build_spy)

    response = await client.post(_vertex_route(flow_id, vertex_id), headers=logged_in_headers)

    assert response.status_code == 503
    build_spy.assert_not_called()


@pytest.mark.security
async def test_should_keep_building_normally_under_a_permissive_policy(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
):
    """The control: with the policy off the seam behaves exactly as before.

    A refusal for everyone would be a denial of service, not a fix.
    """
    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]

    response = await client.post(_vertex_route(flow_id, vertex_id), headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["id"] == vertex_id
