"""Unit tests for the Publora extension bundle (``lfx-publora``).

The components call the Publora REST API with ``httpx``; the tests patch
``httpx.request`` at the API helper module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_publora import PubloraCreatePostComponent, PubloraListConnectionsComponent

REQUEST_PATCH_TARGET = "lfx_publora.components.publora._publora_api.httpx.request"
API_BASE = "https://api.publora.com/api/v1"

CONNECTIONS_PAYLOAD = {
    "success": True,
    "connections": [
        {
            "platformId": "linkedin-ABC123",
            "username": "Jane Doe",
            "displayName": None,
            "connectionStatus": "active",
            "tokenStatus": "valid",
            "tokenExpiresIn": "47d 2h",
            "profileImageUrl": "https://media.publora.com/avatars/linkedin-ABC123.jpg",
        },
        {
            "platformId": "bluesky-did:plc:xyz",
            "username": "jane.bsky.social",
            "displayName": "Jane",
            "connectionStatus": "active",
            "tokenStatus": "valid",
            "tokenExpiresIn": None,
        },
    ],
}


def _response(status_code: int = 200, method: str = "GET", path: str = "/", **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, f"{API_BASE}{path}"), **kwargs)


@pytest.fixture
def connections() -> PubloraListConnectionsComponent:
    c = PubloraListConnectionsComponent()
    c.publora_api_key = "sk_test"  # pragma: allowlist secret
    return c


@pytest.fixture
def create_post() -> PubloraCreatePostComponent:
    c = PubloraCreatePostComponent()
    c.publora_api_key = "sk_test"  # pragma: allowlist secret
    c.content = "Hello from Langflow"
    c.platforms = "linkedin-ABC123"
    c.scheduled_time = ""
    c.media_urls = ""
    c.idempotency_key = ""
    return c


def test_component_class_names_are_stable():
    """Class names must stay stable for saved flows."""
    assert PubloraListConnectionsComponent.__name__ == "PubloraListConnectionsComponent"
    assert PubloraCreatePostComponent.__name__ == "PubloraCreatePostComponent"


def test_list_connections_sends_key_header(connections):
    mock_request = MagicMock(return_value=_response(json=CONNECTIONS_PAYLOAD))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        connections.fetch_connections()
    assert mock_request.call_args.args == ("GET", f"{API_BASE}/platform-connections")
    headers = mock_request.call_args.kwargs["headers"]
    assert headers["x-publora-key"] == "sk_test"  # pragma: allowlist secret
    assert headers["User-Agent"] == "langflow-publora-bundle"
    assert "Content-Type" not in headers
    assert mock_request.call_args.kwargs["json"] is None


def test_list_connections_maps_rows(connections):
    mock_request = MagicMock(return_value=_response(json=CONNECTIONS_PAYLOAD))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        rows = connections.fetch_connections()
    assert [r.data["platformId"] for r in rows] == ["linkedin-ABC123", "bluesky-did:plc:xyz"]
    assert rows[0].text == "linkedin-ABC123 (Jane Doe)"
    assert rows[1].text == "bluesky-did:plc:xyz (Jane)"
    assert "profileImageUrl" not in rows[0].data


def test_list_connections_dataframe_shape(connections):
    mock_request = MagicMock(return_value=_response(json=CONNECTIONS_PAYLOAD))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        frame = connections.publora_list_connections()
    assert len(frame) == 2


def test_list_connections_missing_key_makes_no_request(connections):
    connections.publora_api_key = ""
    mock_request = MagicMock()
    with patch(REQUEST_PATCH_TARGET, mock_request):
        rows = connections.fetch_connections()
    mock_request.assert_not_called()
    assert "Publora API key is required" in rows[0].data["error"]


def test_list_connections_surfaces_api_error(connections):
    mock_request = MagicMock(return_value=_response(401, json={"error": "Invalid API key"}))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        rows = connections.fetch_connections()
    assert rows[0].data["error"] == "Publora API error 401: Invalid API key"


def test_list_connections_rejects_non_object_payload(connections):
    mock_request = MagicMock(return_value=_response(json=["unexpected"]))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        rows = connections.fetch_connections()
    assert "unexpected response" in rows[0].data["error"]


def test_create_post_without_time_is_a_draft(create_post):
    payload = {"success": True, "postGroupId": "pg1", "scheduledTime": None}
    mock_request = MagicMock(return_value=_response(method="POST", path="/create-post", json=payload))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert mock_request.call_args.args == ("POST", f"{API_BASE}/create-post")
    assert mock_request.call_args.kwargs["json"] == {"content": "Hello from Langflow", "platforms": ["linkedin-ABC123"]}
    assert mock_request.call_args.kwargs["headers"]["Content-Type"] == "application/json"
    assert result.data["postGroupId"] == "pg1"
    assert result.data["status"] == "draft"
    assert "saved as a draft" in result.text


def test_create_post_with_time_media_and_several_platforms(create_post):
    create_post.platforms = " linkedin-ABC123,\nbluesky-did:plc:xyz , linkedin-ABC123 "
    create_post.scheduled_time = " 2026-10-14T09:00:00Z "
    create_post.media_urls = "https://example.com/a.png, https://example.com/b.mp4"
    payload = {"success": True, "postGroupId": "pg2", "scheduledTime": "2026-10-14T09:00:00.000Z", "warnings": []}
    mock_request = MagicMock(return_value=_response(method="POST", path="/create-post", json=payload))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert mock_request.call_args.kwargs["json"] == {
        "content": "Hello from Langflow",
        "platforms": ["linkedin-ABC123", "bluesky-did:plc:xyz"],
        "scheduledTime": "2026-10-14T09:00:00Z",
        "mediaUrls": ["https://example.com/a.png", "https://example.com/b.mp4"],
    }
    assert result.data["status"] == "scheduled"
    assert result.data["scheduledTime"] == "2026-10-14T09:00:00.000Z"


def test_create_post_requires_a_platform(create_post):
    create_post.platforms = " , "
    mock_request = MagicMock()
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    mock_request.assert_not_called()
    assert "At least one platformId" in result.data["error"]


def test_create_post_surfaces_api_error(create_post):
    body = {
        "error": ("Invalid platform connection(s): nope-1. Check connected accounts or call GET /platform-connections.")
    }
    mock_request = MagicMock(return_value=_response(400, method="POST", path="/create-post", json=body))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert result.data["error"].startswith("Publora API error 400: Invalid platform connection(s)")


def test_create_post_http_error_without_json_body(create_post):
    mock_request = MagicMock(return_value=_response(502, method="POST", path="/create-post", text="upstream down"))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert result.data["error"] == "Publora API error 502: upstream down"


def test_create_post_http_error_with_empty_body_uses_reason_phrase(create_post):
    mock_request = MagicMock(return_value=_response(502, method="POST", path="/create-post", text=""))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert result.data["error"] == "Publora API error 502: Bad Gateway"


def test_create_post_sends_a_stable_derived_idempotency_key(create_post):
    payload = {"success": True, "postGroupId": "pg1", "scheduledTime": None}
    mock_request = MagicMock(return_value=_response(method="POST", path="/create-post", json=payload))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        create_post.publora_create_post()
        first = mock_request.call_args.kwargs["headers"]["Idempotency-Key"]
        create_post.publora_create_post()
        second = mock_request.call_args.kwargs["headers"]["Idempotency-Key"]
        create_post.content = "A different post"
        create_post.publora_create_post()
        third = mock_request.call_args.kwargs["headers"]["Idempotency-Key"]
    assert first == second
    assert first.startswith("langflow-")
    assert third != first


def test_create_post_uses_a_custom_idempotency_key(create_post):
    create_post.idempotency_key = " run-42 "
    payload = {"success": True, "postGroupId": "pg1", "scheduledTime": None}
    mock_request = MagicMock(return_value=_response(method="POST", path="/create-post", json=payload))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        create_post.publora_create_post()
    assert mock_request.call_args.kwargs["headers"]["Idempotency-Key"] == "run-42"


def test_create_post_wraps_transport_error(create_post):
    mock_request = MagicMock(side_effect=httpx.ConnectError("boom"))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        result = create_post.publora_create_post()
    assert "boom" in result.data["error"]


def test_tool_mode_exposes_publora_specific_tools():
    """Agent-facing tool names must not collide with other components."""
    lister = PubloraListConnectionsComponent(publora_api_key="sk_test")  # pragma: allowlist secret
    poster = PubloraCreatePostComponent(publora_api_key="sk_test")  # pragma: allowlist secret
    assert [t.name for t in asyncio.run(lister.to_toolkit())] == ["publora_list_connections"]
    tools = asyncio.run(poster.to_toolkit())
    assert [t.name for t in tools] == ["publora_create_post"]

    payload = {"success": True, "postGroupId": "pg3", "scheduledTime": None}
    mock_request = MagicMock(return_value=_response(method="POST", path="/create-post", json=payload))
    with patch(REQUEST_PATCH_TARGET, mock_request):
        output = asyncio.run(tools[0].ainvoke({"content": "From an agent", "platforms": "linkedin-ABC123"}))
    assert mock_request.call_args.kwargs["json"] == {"content": "From an agent", "platforms": ["linkedin-ABC123"]}
    assert "pg3" in str(output)
