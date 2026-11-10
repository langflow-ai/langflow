"""Agentic MCP loopback calls must keep the authenticated caller's credentials."""

import asyncio
import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, status
from httpx import ASGITransport, AsyncClient
from httpx import Request as HttpRequest
from langflow.api.v1 import agentic_mcp
from lfx.mcp.client import LangflowClient

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("host", "runtime_port", "root_path", "tls", "cert_hostname", "expected"),
    [
        ("localhost", None, "", False, None, "http://localhost:7860"),
        ("0.0.0.0", 7865, "/langflow", False, None, "http://127.0.0.1:7865/langflow"),  # noqa: S104
        ("::", 7865, "/langflow/", False, None, "http://[::1]:7865/langflow"),
        ("127.0.0.1", None, "/nested/langflow", True, None, "https://127.0.0.1:7860/nested/langflow"),
        ("::1", None, "", True, None, "https://[::1]:7860"),
        ("127.0.0.1", None, "", True, "backend.internal", "https://backend.internal:7860"),
        ("::1", None, "", True, "backend.internal", "https://backend.internal:7860"),
        ("0.0.0.0", None, "", True, "backend.internal", "https://backend.internal:7860"),  # noqa: S104
        ("::", None, "", True, "backend.internal", "https://backend.internal:7860"),
        ("127.0.0.1", None, "", False, "backend.internal", "http://127.0.0.1:7860"),
        ("backend.internal", None, "", False, None, "http://backend.internal:7860"),
    ],
)
async def test_loopback_uses_operator_origin(monkeypatch, host, runtime_port, root_path, tls, cert_hostname, expected):
    settings = SimpleNamespace(
        host=host,
        port=7860,
        runtime_port=runtime_port,
        root_path=root_path,
        ssl_cert_file="cert.pem" if tls else None,
        ssl_key_file="key.pem" if tls else None,
        ssl_cert_hostname=cert_hostname,
    )
    monkeypatch.setattr(
        agentic_mcp,
        "get_settings_service",
        lambda: SimpleNamespace(settings=settings, auth_settings=SimpleNamespace(EXTERNAL_AUTH_ENABLED=False)),
    )
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
        monkeypatch.setattr(
            agentic_mcp,
            "get_settings_service",
            lambda: SimpleNamespace(settings=settings, auth_settings=SimpleNamespace(EXTERNAL_AUTH_ENABLED=False)),
        )
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
    monkeypatch.setattr(
        agentic_mcp,
        "get_settings_service",
        lambda: SimpleNamespace(settings=settings, auth_settings=SimpleNamespace(EXTERNAL_AUTH_ENABLED=False)),
    )
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


@pytest.mark.parametrize("cert_hostname", ["backend.internal", "wrong.internal"])
async def test_loopback_tls_uses_certificate_hostname_and_listener_address(monkeypatch, tmp_path, cert_hostname):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    hostname = "backend.internal"
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
            ssl_cert_hostname=cert_hostname,
        )
        monkeypatch.setattr(
            agentic_mcp,
            "get_settings_service",
            lambda: SimpleNamespace(settings=settings, auth_settings=SimpleNamespace(EXTERNAL_AUTH_ENABLED=False)),
        )
        request = Request(
            {
                "type": "http",
                "scheme": "https",
                "server": ("127.0.0.1", port),
                "path": "/api/v1/agentic/mcp",
                "query_string": b"",
                "headers": [(b"host", b"public.example:9999"), (b"authorization", b"Bearer caller-token")],
            }
        )
        loopback = await agentic_mcp._loopback_client(request)
        try:
            if cert_hostname == hostname:
                assert await loopback.get("/flows/") == {}
            else:
                with pytest.raises(RuntimeError, match="CERTIFICATE_VERIFY_FAILED"):
                    await loopback.get("/flows/")
        finally:
            await loopback.aclose()
    if cert_hostname == hostname:
        assert len(seen) == 1
        assert f"Host: {hostname}:{port}" in seen[0]
        assert "Authorization: Bearer caller-token" in seen[0]
    else:
        assert seen == []


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
        ({"cookie": "access_token_lf=caller-token"}, "", {"Cookie": "access_token_lf=caller-token"}),
        ({}, "x-api-key=caller-key", {"x-api-key": "caller-key"}),
        ({"x-api-key": "caller-key"}, "", {"x-api-key": "caller-key"}),
        ({"x-api-key": "other-key"}, "x-api-key=caller-key", {"x-api-key": "caller-key"}),
        (
            {"authorization": "Bearer caller-token", "x-api-key": "other-key"},
            "x-api-key=third-key",
            {"Authorization": "Bearer caller-token"},
        ),
        ({"authorization": "bearer caller-token"}, "", {"Authorization": "bearer caller-token"}),
        (
            {"authorization": "Basic ignored", "cookie": "access_token_lf=caller-token"},
            "",
            {"Authorization": "Basic ignored", "Cookie": "access_token_lf=caller-token"},
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
    auth_settings = agentic_mcp.get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_ENABLED", True)
    monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_TOKEN_HEADER", "X-External-Auth")
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/",
            "headers": [(b"x-external-auth", b"external-token")],
            "query_string": b"",
        }
    )
    loopback = await agentic_mcp._loopback_client(request)

    assert loopback._headers() == {"Content-Type": "application/json", "X-External-Auth": "external-token"}


@pytest.mark.parametrize("header_name", ["X-External-Auth", "Cookie"])
async def test_explicit_credential_headers_are_copied_and_cannot_follow_another_origin(header_name):
    headers = {header_name: "request-credential"}
    loopback = LangflowClient(server_url="https://backend.example", use_env_global_vars=False, auth_headers=headers)
    headers[header_name] = "later-credential"
    assert loopback._headers()[header_name] == "request-credential"
    with pytest.raises(RuntimeError, match="outside the Langflow server origin"):
        await loopback._check_request_origin(HttpRequest("GET", "https://another.example/"))


@pytest.mark.parametrize("credential_source", ["header", "cookie", "lowercase-authorization"])
@pytest.mark.parametrize("native_credential", [None, "stale", "valid"])
async def test_external_credentials_authenticate_loopback_rest_calls(
    monkeypatch, tmp_path, credential_source, native_credential
):
    from langflow.services.auth import utils as auth_utils
    from langflow.services.auth.context import clear_current_auth_context
    from langflow.services.auth.external import clear_current_external_access_context, identity_from_claims
    from langflow.services.auth.service import AuthService
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_settings_service
    from lfx.services.settings.auth import AuthSettings
    from pydantic import SecretStr

    auth_settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    auth_settings.SECRET_KEY = SecretStr("MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")  # pragma: allowlist secret
    auth_settings.AUTO_LOGIN = False
    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TOKEN_HEADER = "X-External-Auth"  # noqa: S105
    auth_settings.EXTERNAL_AUTH_TOKEN_COOKIE = "external-session"  # noqa: S105
    service_settings = SimpleNamespace(
        settings=get_settings_service().settings.model_copy(deep=True), auth_settings=auth_settings
    )
    service = AuthService(service_settings)
    external_user = User(id=uuid4(), username="external", password="hashed", is_active=True)  # noqa: S106
    native_user = User(id=uuid4(), username="native", password="hashed", is_active=True)  # noqa: S106
    external_token = "external-test-credential"  # noqa: S105  # pragma: allowlist secret
    resolver = AsyncMock(return_value=identity_from_claims({"sub": "external-subject"}, auth_settings))
    monkeypatch.setattr(agentic_mcp, "get_settings_service", lambda: service_settings)
    monkeypatch.setattr(auth_utils, "get_settings_service", lambda: service_settings)
    monkeypatch.setattr(auth_utils, "_auth_service", lambda: service)
    monkeypatch.setattr("langflow.services.auth.service.resolve_external_identity", resolver)
    monkeypatch.setattr("langflow.services.auth.service.get_user_by_id", AsyncMock(return_value=native_user))
    monkeypatch.setattr(service, "_materialize_external_user", AsyncMock(return_value=external_user))
    monkeypatch.setattr(service, "_reconcile_verified_external_groups", AsyncMock())

    headers = {"X-Unrelated-Credential": "must-not-forward"}
    cookies = ["unrelated-session=must-not-forward"]
    if credential_source == "header":
        headers["X-External-Auth"] = external_token
    elif credential_source == "lowercase-authorization":
        auth_settings.EXTERNAL_AUTH_TOKEN_HEADER = "authorization"  # noqa: S105
        headers["authorization"] = f"Bearer {external_token}"
    else:
        cookies.append(f"external-session={external_token}")
    if native_credential:
        native_token = (
            service.create_token({"sub": str(native_user.id), "type": "access"}, timedelta(minutes=5))
            if native_credential == "valid"
            else "stale-native-token"
        )
        cookies.append(f"access_token_lf={native_token}")
    headers["Cookie"] = "; ".join(cookies)

    application = FastAPI()

    @application.get("/api/v1/whoami")
    async def whoami(request: Request):
        assert len(request.headers.getlist("authorization")) <= 1
        user = await auth_utils.get_current_user(
            request, await auth_utils.oauth2_login(request), None, None, db=AsyncMock()
        )
        return {"id": str(user.id)}

    request = Request(
        {
            "type": "http",
            "app": application,
            "server": ("testserver", 80),
            "path": "/api/v1/agentic/mcp",
            "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
            "query_string": b"",
        }
    )
    loopback = await agentic_mcp._loopback_client(request)
    loopback._http = AsyncClient(
        transport=ASGITransport(app=application), event_hooks={"request": [loopback._check_request_origin]}
    )
    try:
        expected_user = (
            native_user
            if native_credential == "valid" and credential_source != "lowercase-authorization"
            else external_user
        )
        assert await loopback.get("/whoami") == {"id": str(expected_user.id)}
        assert "must-not-forward" not in str(loopback._headers())
        if native_credential == "valid" and credential_source != "lowercase-authorization":
            resolver.assert_not_awaited()
        else:
            resolver.assert_awaited_once_with(external_token, auth_settings)
    finally:
        await loopback.aclose()
        clear_current_auth_context()
        clear_current_external_access_context()


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
