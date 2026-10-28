"""Agentic MCP loopback calls must keep the authenticated caller's credentials."""

import asyncio
import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import Request, status
from httpx import AsyncClient
from httpx import Request as HttpRequest
from langflow.api.v1 import agentic_mcp
from lfx.mcp.client import LangflowClient

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("host", "runtime_port", "root_path", "tls", "expected"),
    [
        ("localhost", None, "", False, "http://localhost:7860"),
        ("0.0.0.0", 7865, "/langflow", False, "http://127.0.0.1:7865/langflow"),  # noqa: S104
        ("::", 7865, "/langflow/", False, "http://[::1]:7865/langflow"),
        ("127.0.0.1", None, "/nested/langflow", True, "https://attacker.example:7860/nested/langflow"),
        ("::1", None, "", True, "https://attacker.example:7860"),
        ("backend.internal", None, "", False, "http://backend.internal:7860"),
    ],
)
async def test_loopback_uses_operator_origin(monkeypatch, host, runtime_port, root_path, tls, expected):
    settings = SimpleNamespace(
        host=host,
        port=7860,
        runtime_port=runtime_port,
        root_path=root_path,
        ssl_cert_file="cert.pem" if tls else None,
        ssl_key_file="key.pem" if tls else None,
    )
    monkeypatch.setattr(agentic_mcp, "get_settings_service", lambda: SimpleNamespace(settings=settings))
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": (host, runtime_port or 7860),
            "root_path": "/untrusted-prefix",
            "path": "/api/v1/agentic/mcp",
            "headers": [
                (b"host", b"attacker.example:8902"),
                (b"x-forwarded-host", b"forwarded.example"),
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-prefix", b"/attacker-prefix"),
                (b"authorization", b"Bearer caller-token"),
            ],
            "query_string": b"",
        }
    )
    loopback = await agentic_mcp._loopback_client(request)
    assert loopback.server_url == expected
    assert list(loopback._pinned_ips.values()) == [[{"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)]]  # noqa: S104
    assert loopback._headers()["Authorization"] == "Bearer caller-token"


async def test_loopback_does_not_send_credentials_through_environment_proxy(monkeypatch):
    seen = []

    async def serve(reader, writer):
        seen.append((await reader.readuntil(b"\r\n\r\n")).decode())
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(serve, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        settings = SimpleNamespace(
            host="127.0.0.1", port=port, runtime_port=None, root_path="", ssl_cert_file=None, ssl_key_file=None
        )
        monkeypatch.setattr(agentic_mcp, "get_settings_service", lambda: SimpleNamespace(settings=settings))
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("X-LANGFLOW-GLOBAL-VAR-TEST", "synthetic-value")
        request = Request(
            {
                "type": "http",
                "scheme": "http",
                "server": ("127.0.0.1", port),
                "path": "/api/v1/agentic/mcp",
                "headers": [(b"host", b"attacker.example"), (b"authorization", b"Bearer caller-token")],
                "query_string": b"",
            }
        )
        loopback = await agentic_mcp._loopback_client(request)
        try:
            assert await loopback.get("/flows/") == {}
        finally:
            await loopback.aclose()

    assert len(seen) == 1
    assert f"Host: 127.0.0.1:{port}" in seen[0]
    assert "Authorization: Bearer caller-token" in seen[0]
    assert "X-LANGFLOW-GLOBAL-VAR-TEST: synthetic-value" in seen[0]


async def test_loopback_uses_actual_listener_port(monkeypatch):
    settings = SimpleNamespace(
        host="localhost", port=7860, runtime_port=None, root_path="", ssl_cert_file=None, ssl_key_file=None
    )
    monkeypatch.setattr(agentic_mcp, "get_settings_service", lambda: SimpleNamespace(settings=settings))
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("127.0.0.1", 7861),
            "path": "/api/v1/agentic/mcp",
            "headers": [(b"host", b"attacker.example"), (b"x-forwarded-proto", b"https")],
            "query_string": b"",
        }
    )
    loopback = await agentic_mcp._loopback_client(request)
    assert loopback.server_url == "http://127.0.0.1:7861"


async def test_direct_transport_honors_configured_ca_file(monkeypatch, tmp_path):
    import certifi

    ca_file = tmp_path / "operator-ca.pem"
    ca_file.write_bytes(Path(certifi.where()).read_bytes())
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    create_context = ssl.create_default_context
    with patch("ssl.create_default_context", wraps=create_context) as configured_context:
        loopback = LangflowClient(use_env_proxies=False)
        try:
            await loopback._client()
        finally:
            await loopback.aclose()
    assert any(call.kwargs.get("cafile") == str(ca_file) for call in configured_context.call_args_list)


async def test_loopback_tls_uses_certificate_hostname_and_listener_address(monkeypatch, tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    hostname = "mcp.example.test"
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert_file, key_file)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_file))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    seen = []

    async def serve(reader, writer):
        seen.append((await reader.readuntil(b"\r\n\r\n")).decode())
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(serve, "127.0.0.1", 0, ssl=tls) as server:
        port = server.sockets[0].getsockname()[1]
        settings = SimpleNamespace(
            host="0.0.0.0",  # noqa: S104
            port=7860,
            runtime_port=None,
            root_path="",
            ssl_cert_file=str(cert_file),
            ssl_key_file=str(key_file),
        )
        monkeypatch.setattr(agentic_mcp, "get_settings_service", lambda: SimpleNamespace(settings=settings))
        request = Request(
            {
                "type": "http",
                "scheme": "https",
                "server": ("127.0.0.1", port),
                "path": "/api/v1/agentic/mcp",
                "query_string": b"",
                "headers": [(b"host", f"{hostname}:9999".encode()), (b"authorization", b"Bearer caller-token")],
            }
        )
        loopback = await agentic_mcp._loopback_client(request)
        try:
            assert await loopback.get("/flows/") == {}
        finally:
            await loopback.aclose()
    assert len(seen) == 1
    assert f"Host: {hostname}:{port}" in seen[0]
    assert "Authorization: Bearer caller-token" in seen[0]


@pytest.mark.parametrize("target", ["https://other.example/", "https://local.example:9001/", "http://local.example/"])
async def test_pinned_client_rejects_origin_changes_without_global_variables(target):
    client = LangflowClient(
        server_url="https://local.example", use_env_global_vars=False, pinned_ips={"local.example": ["127.0.0.1"]}
    )
    with pytest.raises(RuntimeError, match="outside the Langflow server origin"):
        await client._check_request_origin(HttpRequest("GET", target))


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

        headers = {**headers, "Accept": "application/json, text/event-stream", "Host": "attacker.example"}

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
