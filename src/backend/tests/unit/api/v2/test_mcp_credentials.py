"""MCP management responses must not disclose the credentials used by runtime clients."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langflow.api.v2.mcp import get_server, router
from langflow.services.auth import utils as auth_utils
from langflow.services.auth.mcp_encryption import encrypt_mcp_config
from langflow.services.auth.service import AuthService
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_settings_service, get_storage_service
from lfx.base.mcp.uvx import mcp_sdk_constraint_args
from lfx.services.deps import injectable_session_scope
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

MASK = "********"
CANARY_CONFIG = {
    "url": "https://mcp.example.invalid/mcp",
    "headers": {"Authorization": "Bearer mcp-canary-header", "x-vendor-key": "mcp-canary-custom"},
    "env": {"VENDOR_TOKEN": "mcp-canary-env", "EMPTY": ""},
}


@pytest.fixture(params=[False, True], ids=["user", "superuser"])
async def credential_api(request, monkeypatch, tmp_path):
    """Exercise the MCP router with a real database and isolated encryption key."""
    auth_settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    auth_settings.SECRET_KEY = SecretStr(Fernet.generate_key().decode())
    settings = SimpleNamespace(settings=SimpleNamespace(), auth_settings=auth_settings)
    auth = AuthService(settings)
    monkeypatch.setattr(auth_utils, "get_auth_service", lambda: auth)
    monkeypatch.setattr("langflow.api.v2.mcp._clear_server_cache", lambda _name: None)
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    user = SimpleNamespace(id=uuid4(), is_superuser=request.param)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        app = FastAPI()
        app.include_router(router, prefix="/api/v2")

        async def db_session():
            """Share the local test transaction with the API dependencies."""
            yield session

        app.dependency_overrides[auth_utils.get_current_active_user] = lambda: user
        app.dependency_overrides[injectable_session_scope] = db_session
        app.dependency_overrides[get_settings_service] = lambda: settings
        app.dependency_overrides[get_storage_service] = lambda: None
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            yield client, session, user
    await engine.dispose()


@pytest.mark.parametrize("encrypted", [False, True], ids=["legacy", "encrypted"])
async def test_get_masks_credentials_and_keeps_runtime_values(credential_api, encrypted):
    """Mask both legacy and encrypted credentials without changing runtime reads."""
    client, session, user = credential_api
    config = encrypt_mcp_config(CANARY_CONFIG) if encrypted else CANARY_CONFIG
    row = MCPServer(user_id=user.id, name="secure", config=config)
    session.add(row)
    await session.commit()

    response = await client.get("/api/v2/mcp/servers/secure")
    assert response.status_code == 200
    assert response.json() == {
        **CANARY_CONFIG,
        "headers": dict.fromkeys(CANARY_CONFIG["headers"], MASK),
        "env": {"VENDOR_TOKEN": MASK, "EMPTY": ""},
    }
    assert "mcp-canary" not in response.text
    assert row.config == config
    assert await get_server("secure", user, session, None, None) == CANARY_CONFIG


async def test_post_masks_credentials_and_encrypts_them_at_rest(credential_api):
    """Persist new map credentials as ciphertext and return masks to the caller."""
    client, session, user = credential_api
    response = await client.post("/api/v2/mcp/servers/secure", json=CANARY_CONFIG)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    assert response.json()["headers"]["Authorization"] == MASK
    row = (await session.exec(select(MCPServer).where(MCPServer.user_id == user.id))).one()
    assert row.config["headers"]["Authorization"].startswith("gAAAAA")
    assert row.config["env"]["VENDOR_TOKEN"].startswith("gAAAAA")
    assert await get_server("secure", user, session, None, None) == CANARY_CONFIG


async def test_patch_roundtrip_preserves_and_replaces_credentials(credential_api):
    """Preserve unchanged masks while honoring credential rotation and removal."""
    client, session, user = credential_api
    await client.post("/api/v2/mcp/servers/secure", json=CANARY_CONFIG)
    fetched = (await client.get("/api/v2/mcp/servers/secure")).json()
    fetched["url"] = "https://mcp.example.invalid/updated"
    fetched["headers"]["x-vendor-key"] = "mcp-canary-rotated"
    del fetched["env"]["EMPTY"]
    response = await client.patch("/api/v2/mcp/servers/secure", json=fetched)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    runtime = await get_server("secure", user, session, None, None)
    assert runtime == {
        "url": fetched["url"],
        "headers": {"Authorization": CANARY_CONFIG["headers"]["Authorization"], "x-vendor-key": "mcp-canary-rotated"},
        "env": {"VENDOR_TOKEN": CANARY_CONFIG["env"]["VENDOR_TOKEN"]},
    }
    # Explicit empty maps still clear the last credential, as the editor expects.
    cleared = await client.patch("/api/v2/mcp/servers/secure", json={"headers": {}, "env": {}})
    assert cleared.status_code == 200
    runtime = await get_server("secure", user, session, None, None)
    assert runtime["headers"] == {}
    assert runtime["env"] == {}


async def test_masked_patch_uses_latest_credential(credential_api):
    """Keep a rotated credential when an older editor submits an unchanged mask."""
    client, session, user = credential_api
    await client.post("/api/v2/mcp/servers/secure", json=CANARY_CONFIG)
    stale_editor = (await client.get("/api/v2/mcp/servers/secure")).json()
    await client.patch(
        "/api/v2/mcp/servers/secure",
        json={"headers": {**CANARY_CONFIG["headers"], "Authorization": "Bearer mcp-canary-new"}},
    )
    response = await client.patch("/api/v2/mcp/servers/secure", json=stale_editor)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    assert (await get_server("secure", user, session, None, None))["headers"][
        "Authorization"
    ] == "Bearer mcp-canary-new"


async def test_unknown_redacted_credential_is_rejected_without_a_write(credential_api):
    """Reject masks that cannot resolve to a stored credential without writing."""
    client, session, user = credential_api
    response = await client.post("/api/v2/mcp/servers/new", json={"headers": {"Authorization": MASK}})
    assert response.status_code == 422
    assert await get_server("new", user, session, None, None) is None
    await client.post("/api/v2/mcp/servers/secure", json=CANARY_CONFIG)
    response = await client.patch("/api/v2/mcp/servers/secure", json={"env": {"NEW_TOKEN": MASK}})
    assert response.status_code == 422
    assert await get_server("secure", user, session, None, None) == CANARY_CONFIG


async def test_credentials_remain_scoped_to_current_user(credential_api):
    """Keep another user's configuration inaccessible, including to superusers."""
    client, session, _user = credential_api
    session.add(MCPServer(user_id=uuid4(), name="other-user", config=CANARY_CONFIG))
    await session.commit()
    assert (await client.get("/api/v2/mcp/servers/other-user")).status_code == 404
    assert (
        await client.patch("/api/v2/mcp/servers/other-user", json={"headers": {"Authorization": MASK}})
    ).status_code == 404


PROJECT_CONFIG = {
    "command": "uvx",
    "args": [
        *mcp_sdk_constraint_args(),
        "mcp-proxy",
        "--transport",
        "streamablehttp",
        "--headers",
        "x-api-key",
        "mcp-canary-project-key",
        "--headers",
        "Authorization",
        "Bearer mcp-canary-project-token",
        "https://mcp.example.invalid/project/streamable",
    ],
}


@pytest.mark.parametrize("encrypted", [False, True], ids=["legacy", "encrypted"])
async def test_project_header_arguments_are_redacted_and_preserved(credential_api, encrypted):
    """Retain generated project credentials through masked edits and flag reordering."""
    client, session, user = credential_api
    config = encrypt_mcp_config(PROJECT_CONFIG) if encrypted else PROJECT_CONFIG
    row = MCPServer(user_id=user.id, name="project", config=config)
    session.add(row)
    await session.commit()
    if encrypted:
        assert "mcp-canary" not in str(row.config)
        assert encrypt_mcp_config(row.config) == row.config

    response = await client.get("/api/v2/mcp/servers/project")
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    editor = response.json()
    assert editor["args"].count(MASK) == 2
    assert await get_server("project", user, session, None, None) == PROJECT_CONFIG
    # Move a repeated header flag without changing its identity. Index-based
    # restoration would pick another argument here, potentially a different key.
    args = editor["args"]
    header_index = args.index("--headers")
    args[header_index : header_index + 6] = (
        args[header_index + 3 : header_index + 6] + args[header_index : header_index + 3]
    )
    patched = await client.patch("/api/v2/mcp/servers/project", json=editor)
    assert patched.status_code == 200
    assert "mcp-canary" not in patched.text
    runtime = await get_server("project", user, session, None, None)
    assert runtime["args"][header_index + 2] == "Bearer mcp-canary-project-token"
    assert runtime["args"][header_index + 5] == "mcp-canary-project-key"
    # Removing a header must remove its credential too, even as indexes shift.
    del editor["args"][header_index : header_index + 3]
    patched = await client.patch("/api/v2/mcp/servers/project", json=editor)
    assert patched.status_code == 200
    assert "mcp-canary" not in patched.text
    runtime = await get_server("project", user, session, None, None)
    assert "Authorization" not in runtime["args"]
    assert "mcp-canary-project-key" in runtime["args"]
    assert "Bearer mcp-canary-project-token" not in runtime["args"]


async def test_project_argument_masks_preserve_rotation_and_reject_deleted_or_renamed_headers(credential_api):
    """Resolve current argument credentials and reject masks for removed headers."""
    client, session, user = credential_api
    response = await client.post("/api/v2/mcp/servers/project", json=PROJECT_CONFIG)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    editor = (await client.get("/api/v2/mcp/servers/project")).json()
    rotated = {**PROJECT_CONFIG, "args": list(PROJECT_CONFIG["args"])}
    key_index = rotated["args"].index("--headers") + 2
    rotated["args"][key_index] = "mcp-canary-rotated-project-key"
    await client.patch("/api/v2/mcp/servers/project", json=rotated)
    response = await client.patch("/api/v2/mcp/servers/project", json=editor)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    runtime = await get_server("project", user, session, None, None)
    assert runtime["args"][key_index] == "mcp-canary-rotated-project-key"
    editor["args"][key_index - 1] = "other-header"
    assert (await client.patch("/api/v2/mcp/servers/project", json=editor)).status_code == 422
    assert await get_server("project", user, session, None, None) == runtime
    editor = (await client.get("/api/v2/mcp/servers/project")).json()
    assert (await client.patch("/api/v2/mcp/servers/project", json={"args": []})).status_code == 200
    assert (await client.patch("/api/v2/mcp/servers/project", json=editor)).status_code == 422
    assert (await get_server("project", user, session, None, None))["args"] == []


async def test_duplicate_header_argument_masks_require_matching_occurrences(credential_api):
    """Preserve repeated header values without guessing after duplicate removal."""
    client, session, user = credential_api
    config = {
        "command": "uvx",
        "args": [
            "mcp-proxy",
            "--headers",
            "X-Token",
            "mcp-canary-first",
            "--headers",
            "x-token",
            "mcp-canary-second",
            "https://mcp.example.invalid",
        ],
    }
    response = await client.post("/api/v2/mcp/servers/duplicates", json=config)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    editor = (await client.get("/api/v2/mcp/servers/duplicates")).json()
    assert (await client.patch("/api/v2/mcp/servers/duplicates", json=editor)).status_code == 200
    assert await get_server("duplicates", user, session, None, None) == config
    del editor["args"][1:4]
    assert (await client.patch("/api/v2/mcp/servers/duplicates", json=editor)).status_code == 422
    assert await get_server("duplicates", user, session, None, None) == config


async def test_new_redacted_header_arguments_are_rejected(credential_api):
    """Reject placeholder argument credentials when creating a new server."""
    client, session, user = credential_api
    response = await client.post(
        "/api/v2/mcp/servers/new",
        json={"command": "uvx", "args": ["mcp-proxy", "--headers", "x-api-key", MASK, "https://mcp.example.invalid"]},
    )
    assert response.status_code == 422
    assert await get_server("new", user, session, None, None) is None


async def test_post_and_patch_encrypt_header_arguments_at_rest(credential_api):
    """Encrypt repeated argv credentials on both creation and rotation, preserving runtime values."""
    client, session, user = credential_api
    response = await client.post("/api/v2/mcp/servers/project", json=PROJECT_CONFIG)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    row = (await session.exec(select(MCPServer).where(MCPServer.user_id == user.id, MCPServer.name == "project"))).one()
    header_index = PROJECT_CONFIG["args"].index("--headers")
    for index in [header_index + 2, header_index + 5]:
        assert row.config["args"][index].startswith("gAAAAA")
        assert row.config["args"][index] != PROJECT_CONFIG["args"][index]
    assert "mcp-canary" not in str(row.config)
    assert await get_server("project", user, session, None, None) == PROJECT_CONFIG

    rotated = {**PROJECT_CONFIG, "args": list(PROJECT_CONFIG["args"])}
    rotated["args"][header_index + 2] = "mcp-canary-new-project-key"
    rotated["args"][-1:-1] = ["--headers", "X-New-Token", "mcp-canary-added-token", "--headers", "X-Empty", ""]
    response = await client.patch("/api/v2/mcp/servers/project", json=rotated)
    assert response.status_code == 200
    assert "mcp-canary" not in response.text
    await session.refresh(row)
    positions = [index + 2 for index, value in enumerate(rotated["args"]) if value == "--headers"]
    for index in positions:
        if rotated["args"][index]:
            assert row.config["args"][index].startswith("gAAAAA")
            assert row.config["args"][index] != rotated["args"][index]
        else:
            assert row.config["args"][index] == ""
    assert "mcp-canary" not in str(row.config)
    assert await get_server("project", user, session, None, None) == rotated


async def test_public_server_listing_returns_only_metadata(credential_api):
    """Keep public listings free of credentials while internal reads remain runnable."""
    client, session, user = credential_api
    await client.post("/api/v2/mcp/servers/secure", json=CANARY_CONFIG)
    await client.post("/api/v2/mcp/servers/project", json=PROJECT_CONFIG)
    response = await client.get("/api/v2/mcp/servers")
    assert response.status_code == 200
    assert response.json() == [
        {"name": "secure", "mode": None, "toolsCount": None},
        {"name": "project", "mode": None, "toolsCount": None},
    ]
    assert "mcp-canary" not in response.text
    assert await get_server("secure", user, session, None, None) == CANARY_CONFIG
    assert await get_server("project", user, session, None, None) == PROJECT_CONFIG
