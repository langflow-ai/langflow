"""Projects whose names share the truncated MCP server name prefix must not block each other.

Every project auto-registers an MCP server named ``lf-<first 26 sanitized chars>``. Two distinct
project names with the same first 26 characters derive the same server name, which used to make
the second project creation fail with a 409.
"""

from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

PROJECT_A = "Marketing Automation Project Alpha"
PROJECT_B = "Marketing Automation Project Beta"
SHARED_SERVER_NAME = "lf-marketing_automation_proje"


async def _servers_by_project(client: AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    """Map project id -> MCP server name for every server that points at a project URL."""
    response = await client.get("api/v2/mcp/servers", params={"action_count": False}, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    servers: dict[str, str] = {}
    for server in response.json():
        config = (await client.get(f"api/v2/mcp/servers/{server['name']}", headers=headers)).json() or {}
        for arg in config.get("args", []):
            if isinstance(arg, str) and "/api/v1/mcp/project/" in arg:
                project_id = arg.split("/api/v1/mcp/project/")[1].split("/")[0]
                servers[str(UUID(project_id))] = server["name"]
    return servers


async def _create_project(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("api/v1/projects/", json={"name": name}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["name"] == name
    return response.json()["id"]


@pytest.mark.asyncio
async def test_should_create_both_projects_when_names_share_mcp_server_name_prefix(
    client: AsyncClient, logged_in_headers
):
    project_a = await _create_project(client, logged_in_headers, PROJECT_A)

    response = await client.post("api/v1/projects/", json={"name": PROJECT_B}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    project_b = response.json()["id"]
    servers = await _servers_by_project(client, logged_in_headers)
    assert servers[project_a] == SHARED_SERVER_NAME
    assert servers[project_b] != SHARED_SERVER_NAME
    assert servers[project_b].startswith("lf-marketing_automat-")
    assert len(servers[project_b]) <= len(SHARED_SERVER_NAME)


@pytest.mark.asyncio
async def test_should_keep_existing_server_name_when_project_has_no_prefix_collision(
    client: AsyncClient, logged_in_headers
):
    project_id = await _create_project(client, logged_in_headers, PROJECT_A)

    servers = await _servers_by_project(client, logged_in_headers)

    assert servers[project_id] == SHARED_SERVER_NAME


@pytest.mark.asyncio
async def test_should_remove_each_projects_own_server_when_prefix_owner_is_deleted_first(
    client: AsyncClient, logged_in_headers
):
    project_a = await _create_project(client, logged_in_headers, PROJECT_A)
    project_b = await _create_project(client, logged_in_headers, PROJECT_B)

    delete_a = await client.delete(f"api/v1/projects/{project_a}", headers=logged_in_headers)
    delete_b = await client.delete(f"api/v1/projects/{project_b}", headers=logged_in_headers)

    assert delete_a.status_code == status.HTTP_204_NO_CONTENT
    assert delete_b.status_code == status.HTTP_204_NO_CONTENT
    servers = await _servers_by_project(client, logged_in_headers)
    assert project_a not in servers
    assert project_b not in servers


@pytest.mark.asyncio
async def test_should_move_disambiguated_server_when_project_is_renamed(client: AsyncClient, logged_in_headers):
    await _create_project(client, logged_in_headers, PROJECT_A)
    project_b = await _create_project(client, logged_in_headers, PROJECT_B)
    old_server_name = (await _servers_by_project(client, logged_in_headers))[project_b]

    response = await client.patch(
        f"api/v1/projects/{project_b}", json={"name": "Quarterly Reports"}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    servers = await _servers_by_project(client, logged_in_headers)
    assert servers[project_b] == "lf-quarterly_reports"
    assert old_server_name not in servers.values()


@pytest.mark.asyncio
async def test_should_rename_into_a_taken_prefix_without_conflict(client: AsyncClient, logged_in_headers):
    project_a = await _create_project(client, logged_in_headers, PROJECT_A)
    project_c = await _create_project(client, logged_in_headers, "Quarterly Reports")

    response = await client.patch(f"api/v1/projects/{project_c}", json={"name": PROJECT_B}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    servers = await _servers_by_project(client, logged_in_headers)
    assert servers[project_a] == SHARED_SERVER_NAME
    assert servers[project_c].startswith("lf-marketing_automat-")
    assert servers[project_c] != SHARED_SERVER_NAME
