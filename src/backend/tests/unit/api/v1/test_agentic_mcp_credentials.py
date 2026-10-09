"""Agentic MCP loopback calls must keep the authenticated caller's credentials."""

import json
from unittest.mock import patch

import pytest
from fastapi import Request, status
from httpx import AsyncClient
from langflow.api.v1 import agentic_mcp
from lfx.mcp.client import LangflowClient

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("headers", "query", "expected_auth"),
    [
        ({"cookie": "access_token_lf=caller-token"}, "", {"Authorization": "Bearer caller-token"}),
        ({}, "x-api-key=caller-key", {"x-api-key": "caller-key"}),
        ({"x-api-key": "caller-key"}, "", {"x-api-key": "caller-key"}),
        ({"x-api-key": "other-key"}, "x-api-key=caller-key", {"x-api-key": "caller-key"}),
        (
            {"authorization": "Bearer caller-token", "x-api-key": "other-key"},
            "x-api-key=third-key",
            {"Authorization": "Bearer caller-token"},
        ),
        ({"authorization": "bearer caller-token"}, "", {"Authorization": "Bearer caller-token"}),
        (
            {"authorization": "Basic ignored", "cookie": "access_token_lf=caller-token"},
            "",
            {"Authorization": "Bearer caller-token"},
        ),
        ({}, "", {}),
        ({"x-api-key": ""}, "x-api-key=", {}),
    ],
)
async def test_loopback_uses_only_request_credentials(monkeypatch, headers, query, expected_auth):
    monkeypatch.setenv("LANGFLOW_API_KEY", "server-key")
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/api/v1/agentic/mcp",
            "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
            "query_string": query.encode(),
        }
    )
    loopback = await agentic_mcp._loopback_client(request)

    assert loopback._headers() == {"Content-Type": "application/json", **expected_auth}


async def test_loopback_preserves_external_token(monkeypatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", "server-key")
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/",
            "headers": [],
            "query_string": b"",
        }
    )
    with patch("langflow.services.auth.utils._get_external_token", return_value="external-token"):
        loopback = await agentic_mcp._loopback_client(request)

    assert loopback._headers() == {"Content-Type": "application/json", "Authorization": "Bearer external-token"}


@pytest.mark.parametrize(
    "credential_source",
    ["cookie", "query", "header", "bearer", "query_over_header", "cookie_over_key", "bearer_over_cookie"],
)
async def test_mcp_tools_cannot_read_or_delete_another_users_flow(
    client,
    logged_in_headers,
    created_api_key,
    monkeypatch,
    credential_source,
):
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_auth_service, get_settings_service, session_scope

    monkeypatch.setattr(get_settings_service().auth_settings, "API_KEY_SOURCE", "db")
    async with session_scope() as db:
        admin = User(
            username="mcp-admin",
            password=get_auth_service().get_password_hash("testpassword"),
            is_active=True,
            is_superuser=True,
        )
        db.add(admin)
        await db.flush()
        admin_id = admin.id
        tokens = await get_auth_service().create_user_tokens(user_id=admin_id, db=db)
    admin_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    key_response = await client.post("/api/v1/api_key/", headers=admin_headers, json={"name": "server-key"})
    assert key_response.status_code == status.HTTP_200_OK
    admin_key = key_response.json()["api_key"]
    monkeypatch.setenv("LANGFLOW_API_KEY", admin_key)

    for name, headers in [("admin-private", admin_headers), ("caller-owned", logged_in_headers)]:
        response = await client.post(
            "/api/v1/flows/", headers=headers, json={"name": name, "data": {"nodes": [], "edges": []}}
        )
        assert response.status_code == status.HTTP_201_CREATED
        if name == "admin-private":
            admin_flow_id = response.json()["id"]
        else:
            caller_flow_id = response.json()["id"]

    # Login and flow creation populate the HTTP client's cookie jar. Use fresh
    # clients so each parameter exercises exactly its named authentication source.
    async with (
        AsyncClient(transport=client._transport, base_url="http://testserver/") as caller,
        AsyncClient(transport=client._transport, base_url="http://testserver/") as loopback_http,
    ):
        headers = {}
        params = {}
        if credential_source in {"cookie", "cookie_over_key"}:
            token = logged_in_headers["Authorization"].removeprefix("Bearer ")
            headers = {"Cookie": f"access_token_lf={token}"}
            if credential_source == "cookie_over_key":
                headers["x-api-key"] = admin_key
        elif credential_source in {"query", "query_over_header"}:
            params = {"x-api-key": created_api_key.api_key}
            if credential_source == "query_over_header":
                headers["x-api-key"] = admin_key
        elif credential_source == "header":
            headers = {"x-api-key": created_api_key.api_key}
        else:
            headers = dict(logged_in_headers)
            if credential_source == "bearer_over_cookie":
                headers["Cookie"] = f"access_token_lf={tokens['access_token']}"

        direct = await caller.get("/api/v1/flows/", headers=headers, params=params)
        assert direct.status_code == status.HTTP_200_OK
        assert "caller-owned" in {flow["name"] for flow in direct.json()}
        assert "admin-private" not in {flow["name"] for flow in direct.json()}
        denied = await caller.delete(f"/api/v1/flows/{admin_flow_id}", headers=headers, params=params)
        assert denied.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

        headers = {**headers, "Accept": "application/json, text/event-stream"}

        async def get_http(_self):
            return loopback_http

        async def call_tool(name, arguments):
            response = await caller.post(
                "/api/v1/agentic/mcp",
                headers=headers,
                params=params,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            assert response.status_code == status.HTTP_200_OK
            messages = [
                json.loads(line.removeprefix("data: "))
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            return next(message["result"] for message in messages if message.get("id") == 1)

        with patch.object(LangflowClient, "_client", get_http):
            listed = await call_tool("list_flows", {})
            assert not listed.get("isError")
            text = " ".join(item.get("text", "") for item in listed["content"])
            assert "caller-owned" in text
            assert "admin-private" not in text
            deleted = await call_tool("delete_flow", {"flow_id": admin_flow_id})
            assert deleted["isError"] is True
            deletion_text = " ".join(item.get("text", "") for item in deleted["content"])
            assert "failed" in deletion_text
            own_deletion = await call_tool("delete_flow", {"flow_id": caller_flow_id})
            assert not own_deletion.get("isError")

        still_exists = await caller.get(f"/api/v1/flows/{admin_flow_id}", headers=admin_headers)
        assert still_exists.status_code == status.HTTP_200_OK
        own_flow = await caller.get(f"/api/v1/flows/{caller_flow_id}", headers=logged_in_headers)
        assert own_flow.status_code == status.HTTP_404_NOT_FOUND
