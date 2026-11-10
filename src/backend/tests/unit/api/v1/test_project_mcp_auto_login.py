import json
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from langflow.api.v1.mcp_projects import init_mcp_servers, verify_project_auth
from langflow.api.v2.mcp import get_server
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from lfx.base.mcp.util import project_mcp_server_name
from lfx.base.mcp.uvx import mcp_sdk_constraint_args
from sqlmodel import select


def _set_auto_login(monkeypatch, *, skip_auth: bool, superuser: str) -> None:
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "AUTO_LOGIN", True)
    monkeypatch.setattr(settings.auth_settings, "skip_auth_auto_login", skip_auth)
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER", superuser)
    monkeypatch.setattr(settings.settings, "add_projects_to_mcp_servers", True)
    monkeypatch.setattr(settings.settings, "mcp_composer_enabled", False)


async def _project_config(project_id: UUID, owner):
    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        assert project is not None
        config = await get_server(
            project_mcp_server_name(project.name), owner, session, get_storage_service(), get_settings_service()
        )
        return project.auth_settings, config


async def _assert_authenticated_config(project_id: UUID, owner) -> str:
    auth, config = await _project_config(project_id, owner)
    assert auth == {"auth_type": "apikey"}
    assert config is not None
    args = config["args"]
    api_key = args[args.index("x-api-key") + 1]
    authenticated = await verify_project_auth(project_id, query_param=None, header_param=api_key)
    assert authenticated.id == owner.id
    with pytest.raises(HTTPException) as exc:
        await verify_project_auth(project_id, query_param=None, header_param=None)
    assert exc.value.status_code == 401
    return api_key


@pytest.mark.parametrize("creation", ["post", "upsert", "upload", "replacement"])
@pytest.mark.usefixtures("administrator_user")
async def test_auto_login_project_clients_authenticate_without_skip_auth(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch, creation
):
    _set_auto_login(monkeypatch, skip_auth=False, superuser=active_user.username)
    name = f"mcp-auto-{uuid4().hex[:12]}"
    project_id = uuid4()
    if creation == "post":
        response = await client.post("api/v1/projects/", json={"name": name}, headers=logged_in_headers)
        assert response.status_code == 201, response.text
        project_id = UUID(response.json()["id"])
    elif creation == "upsert":
        response = await client.put(f"api/v1/projects/{project_id}", json={"name": name}, headers=logged_in_headers)
        assert response.status_code == 201, response.text
    elif creation == "upload":
        response = await client.post(
            "api/v1/projects/upload/",
            files={"file": ("project.json", json.dumps({"folder_name": name, "flows": []}), "application/json")},
            headers=logged_in_headers,
        )
        assert response.status_code == 201, response.text
        async with session_scope() as session:
            project = (
                await session.exec(select(Folder).where(Folder.user_id == active_user.id, Folder.name == name))
            ).one()
            project_id = project.id
            assert project.auth_settings == {"auth_type": "apikey"}
        await init_mcp_servers()
    else:
        response = await client.put(
            f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
            json={"project_name": name, "description": "", "flows": []},
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.text
    await _assert_authenticated_config(project_id, active_user)


@pytest.mark.usefixtures("administrator_user")
async def test_explicit_public_project_stays_public_under_auto_login(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch
):
    _set_auto_login(monkeypatch, skip_auth=False, superuser=active_user.username)
    response = await client.post(
        "api/v1/projects/",
        json={"name": f"mcp-public-{uuid4().hex[:12]}", "auth_settings": {"auth_type": "none"}},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    project_id = UUID(response.json()["id"])
    await init_mcp_servers()
    auth, config = await _project_config(project_id, active_user)
    assert auth == {"auth_type": "none"}
    assert "x-api-key" not in config["args"]
    owner = await verify_project_auth(project_id, query_param=None, header_param=None)
    assert owner.id == active_user.id


@pytest.mark.parametrize("owns_superuser", [False, True])
@pytest.mark.usefixtures("administrator_user")
async def test_skip_auth_default_only_applies_to_the_configured_superuser(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch, owns_superuser
):
    _set_auto_login(monkeypatch, skip_auth=True, superuser=active_user.username if owns_superuser else "another-admin")
    response = await client.post(
        "api/v1/projects/", json={"name": f"mcp-skip-{uuid4().hex[:12]}"}, headers=logged_in_headers
    )
    assert response.status_code == 201, response.text
    project_id = UUID(response.json()["id"])
    if not owns_superuser:
        await _assert_authenticated_config(project_id, active_user)
        return
    auth, config = await _project_config(project_id, active_user)
    assert auth is None
    assert "x-api-key" not in config["args"]
    owner = await verify_project_auth(project_id, query_param=None, header_param=None)
    assert owner.id == active_user.id


@pytest.mark.parametrize("existing_auth_type", [None, "oauth"])
@pytest.mark.usefixtures("administrator_user")
async def test_startup_repairs_keyless_client_once(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch, existing_auth_type
):
    _set_auto_login(monkeypatch, skip_auth=False, superuser=active_user.username)
    project_id = uuid4()
    name = f"mcp-legacy-{uuid4().hex[:12]}"
    async with session_scope() as session:
        session.add(
            Folder(
                id=project_id,
                name=name,
                user_id=active_user.id,
                auth_settings={"auth_type": existing_auth_type} if existing_auth_type else None,
            )
        )
    response = await client.post(
        f"api/v2/mcp/servers/{project_mcp_server_name(name)}",
        json={
            "command": "uvx",
            "args": [
                *mcp_sdk_constraint_args(),
                "mcp-proxy",
                "--transport",
                "streamablehttp",
                f"http://localhost:7860/api/v1/mcp/project/{project_id}/streamable",
            ],
        },
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    await init_mcp_servers()
    first_key = await _assert_authenticated_config(project_id, active_user)
    async with session_scope() as session:
        first_keys = (await session.exec(select(ApiKey.id).where(ApiKey.user_id == active_user.id))).all()
    await init_mcp_servers()
    second_key = await _assert_authenticated_config(project_id, active_user)
    async with session_scope() as session:
        second_keys = (await session.exec(select(ApiKey.id).where(ApiKey.user_id == active_user.id))).all()
    assert second_key == first_key
    assert set(second_keys) == set(first_keys)
