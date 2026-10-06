"""Authorization regressions for deprecated V1 vertex routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from unittest.mock import MagicMock

import pytest
from langflow.services.deps import get_chat_service
from lfx.graph.graph.base import Graph
from lfx.services.model_provider_policy import current_model_provider_policy_context

if TYPE_CHECKING:
    from httpx import AsyncClient, Response

RouteName = Literal["order", "build", "stream"]
CacheState = Literal["empty", "owner_seeded"]


async def _login_second_user(client: AsyncClient, user_two) -> dict[str, str]:
    response = await client.post(
        "api/v1/login",
        data={"username": user_two.username, "password": "hashed_password"},  # pragma: allowlist secret
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _request_route(
    client: AsyncClient,
    *,
    route_name: RouteName,
    flow_id: str,
    vertex_id: str,
    headers: dict[str, str],
) -> Response:
    if route_name == "order":
        return await client.post(f"api/v1/build/{flow_id}/vertices", headers=headers)
    if route_name == "build":
        return await client.post(f"api/v1/build/{flow_id}/vertices/{vertex_id}", headers=headers)
    return await client.get(f"api/v1/build/{flow_id}/{vertex_id}/stream", headers=headers)


@pytest.mark.security
@pytest.mark.parametrize("cache_state", ["empty", "owner_seeded"])
@pytest.mark.parametrize("route_name", ["order", "build", "stream"])
async def test_non_owner_public_flow_is_hidden_from_deprecated_vertex_routes(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    user_two,
    monkeypatch: pytest.MonkeyPatch,
    route_name: RouteName,
    cache_state: CacheState,
):
    """A PUBLIC transition must not widen the owner-only legacy vertex surface."""
    from langflow.api.v1 import chat as chat_module

    flow_id = added_flow_webhook_test["id"]
    vertex_id = added_flow_webhook_test["data"]["nodes"][0]["id"]
    other_headers = await _login_second_user(client, user_two)

    # Capture the exact same-flow privacy response while it is still PRIVATE.
    private_response = await _request_route(
        client,
        route_name=route_name,
        flow_id=flow_id,
        vertex_id=vertex_id,
        headers=other_headers,
    )
    assert private_response.status_code == 404

    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == 200

    chat_service = get_chat_service()
    await chat_service.clear_cache(str(flow_id))
    if cache_state == "owner_seeded":
        seed_response = await client.post(f"api/v1/build/{flow_id}/vertices", headers=logged_in_headers)
        assert seed_response.status_code == 200
        vertex_id = seed_response.json()["ids"][0]

    # Owner-only denial must happen before touching the flow-keyed graph cache
    # or any MemoryBase owner/backend credential seam.
    get_chat_service_spy = MagicMock(wraps=chat_module.get_chat_service)
    monkeypatch.setattr(chat_module, "get_chat_service", get_chat_service_spy)

    public_response = await _request_route(
        client,
        route_name=route_name,
        flow_id=flow_id,
        vertex_id=vertex_id,
        headers=other_headers,
    )

    get_chat_service_spy.assert_not_called()
    assert public_response.status_code == private_response.status_code == 404
    assert public_response.json() == private_response.json() == {"detail": f"Flow with id {flow_id} not found"}


@pytest.mark.security
async def test_owner_keeps_all_deprecated_vertex_routes_after_public_transition(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
):
    """Making a flow PUBLIC must not break its owner's legacy editor path."""
    flow_id = added_flow_webhook_test["id"]
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == 200

    order_response = await client.post(f"api/v1/build/{flow_id}/vertices", headers=logged_in_headers)
    assert order_response.status_code == 200
    vertex_id = order_response.json()["ids"][0]

    build_response = await client.post(
        f"api/v1/build/{flow_id}/vertices/{vertex_id}",
        json={"inputs": {"input_value": "owner input", "session": "owner-session"}},
        headers=logged_in_headers,
    )
    assert build_response.status_code == 200

    async with client.stream(
        "GET",
        f"api/v1/build/{flow_id}/{vertex_id}/stream",
        headers=logged_in_headers,
    ) as stream_response:
        assert stream_response.status_code == 200
        await stream_response.aread()


@pytest.mark.security
async def test_owner_deprecated_vertex_routes_bind_stored_flow_provider_scope(
    client: AsyncClient,
    added_flow_webhook_test,
    logged_in_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    """Cold builds, warm vertex builds, and SSE iteration reuse the trusted flow scope."""
    from langflow.api.v1 import chat as chat_module

    captured = {}
    original_build_graph = chat_module.build_graph_from_db
    original_build_vertex = Graph.build_vertex

    async def capture_graph_scope(*args, **kwargs):
        captured["order"] = current_model_provider_policy_context()
        return await original_build_graph(*args, **kwargs)

    async def capture_vertex_scope(self, *args, **kwargs):
        captured["build"] = current_model_provider_policy_context()
        return await original_build_vertex(self, *args, **kwargs)

    async def capture_stream_scope(*_args, **_kwargs):
        captured["stream"] = current_model_provider_policy_context()
        yield 'event: close\ndata: {"message": "Stream closed"}\n\n'

    monkeypatch.setattr(chat_module, "build_graph_from_db", capture_graph_scope)
    monkeypatch.setattr(Graph, "build_vertex", capture_vertex_scope)
    monkeypatch.setattr(chat_module, "_stream_vertex", capture_stream_scope)

    flow_id = added_flow_webhook_test["id"]
    order_response = await client.post(f"api/v1/build/{flow_id}/vertices", headers=logged_in_headers)
    assert order_response.status_code == 200, order_response.text
    vertex_id = order_response.json()["ids"][0]

    build_response = await client.post(
        f"api/v1/build/{flow_id}/vertices/{vertex_id}",
        headers=logged_in_headers,
    )
    assert build_response.status_code == 200, build_response.text

    async with client.stream(
        "GET",
        f"api/v1/build/{flow_id}/{vertex_id}/stream",
        headers=logged_in_headers,
    ) as stream_response:
        assert stream_response.status_code == 200
        await stream_response.aread()

    for route in ("order", "build", "stream"):
        attributes = captured[route].attributes
        assert attributes["provider_scope_required"] is True
        assert str(attributes["project_id"]) == added_flow_webhook_test["folder_id"]
