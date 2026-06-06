"""Lothal API tests.

Story A.1 declared the full `/api/v1/lothal/` surface as typed `501` stubs.
Story B.2 lights up the project CRUD (`POST`/`GET`/`GET {id}`/`DELETE` on
`/projects`), so those four routes now have behaviour tests; every other
endpoint is still a stub and is asserted to return the structured `501`.

Common to both: every endpoint requires auth and appears in the OpenAPI schema.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.lothal_project.model import Project
from langflow.services.deps import session_scope

# A non-existent project id is fine for the stubbed routes: they short-circuit
# before any lookup.
PROJECT_ID = "00000000-0000-0000-0000-000000000000"

# (method, path, json body) for the endpoints still backed by a `501` stub.
# Bodies are valid so the only thing that can fail is auth (401/403) or the stub
# itself (501) — never request validation (422).
STUBBED_ENDPOINTS = [
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/chat", {"content": "hi"}),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/messages", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/prd", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/diagram", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/diagram/save", {"nodes": [], "edges": []}),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/diagram/approve", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/code", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/download", None),
    ("POST", "api/v1/lothal/debug/llm", {"message": "ping"}),
]

# The project CRUD routes that went live in B.2. Still require auth, but no
# longer return `501`.
LIVE_PROJECT_ENDPOINTS = [
    ("POST", "api/v1/lothal/projects/", {"name": "My App"}),
    ("GET", "api/v1/lothal/projects/", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("DELETE", f"api/v1/lothal/projects/{PROJECT_ID}", None),
]

ALL_ENDPOINTS = LIVE_PROJECT_ENDPOINTS + STUBBED_ENDPOINTS


@pytest.mark.parametrize(("method", "path", "json_body"), STUBBED_ENDPOINTS)
async def test_stub_returns_structured_501(
    client: AsyncClient,
    logged_in_headers: dict,
    method: str,
    path: str,
    json_body: dict | None,
):
    response = await client.request(method, path, json=json_body, headers=logged_in_headers)

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    body = response.json()
    assert body["status"] == "not_implemented"
    assert isinstance(body["detail"], str)
    assert body["detail"]


@pytest.mark.parametrize(("method", "path", "json_body"), ALL_ENDPOINTS)
async def test_endpoint_requires_auth(
    client: AsyncClient,
    method: str,
    path: str,
    json_body: dict | None,
):
    response = await client.request(method, path, json=json_body)

    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_openapi_lists_full_lothal_surface(client: AsyncClient):
    response = await client.get("openapi.json")
    assert response.status_code == status.HTTP_200_OK
    paths = response.json()["paths"]

    expected = {
        "/api/v1/lothal/projects/",
        "/api/v1/lothal/projects/{project_id}",
        "/api/v1/lothal/projects/{project_id}/chat",
        "/api/v1/lothal/projects/{project_id}/messages",
        "/api/v1/lothal/projects/{project_id}/prd",
        "/api/v1/lothal/projects/{project_id}/diagram",
        "/api/v1/lothal/projects/{project_id}/diagram/save",
        "/api/v1/lothal/projects/{project_id}/diagram/approve",
        "/api/v1/lothal/projects/{project_id}/code",
        "/api/v1/lothal/projects/{project_id}/download",
        "/api/v1/lothal/debug/llm",
    }
    assert expected <= set(paths)

    # A still-stubbed route documents the structured 501 in its responses.
    assert "501" in paths["/api/v1/lothal/debug/llm"]["post"]["responses"]


# --- Project CRUD (Story B.2) -------------------------------------------------


async def test_create_list_get_delete_project(client: AsyncClient, logged_in_headers: dict):
    # Create — a fresh project starts in CLARIFICATION with empty artifacts.
    response = await client.post("api/v1/lothal/projects/", json={"name": "My App"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()
    assert project["name"] == "My App"
    assert project["phase"] == "CLARIFICATION"
    assert project["prd_content"] is None
    assert project["diagram_mmd"] is None
    assert project["diagram_layout"] is None
    project_id = project["id"]

    # List — includes the new project.
    response = await client.get("api/v1/lothal/projects/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert project_id in [p["id"] for p in response.json()]

    # Get — returns the same project.
    response = await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == project_id

    # Delete — 204, then it's gone.
    response = await client.delete(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_create_project_rejects_blank_name(client: AsyncClient, logged_in_headers: dict):
    response = await client.post("api/v1/lothal/projects/", json={"name": "   "}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_get_or_delete_missing_project_is_404(client: AsyncClient, logged_in_headers: dict):
    assert (
        await client.get(f"api/v1/lothal/projects/{PROJECT_ID}", headers=logged_in_headers)
    ).status_code == status.HTTP_404_NOT_FOUND
    assert (
        await client.delete(f"api/v1/lothal/projects/{PROJECT_ID}", headers=logged_in_headers)
    ).status_code == status.HTTP_404_NOT_FOUND


async def test_projects_are_scoped_to_the_owner(client: AsyncClient, logged_in_headers: dict, user_two):
    # Seed a project owned by a different user directly in the DB.
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id)
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id  # UUID primary key, for cleanup
        foreign_id = str(foreign_pk)  # string form, for URL paths

    try:
        # The logged-in user can't see another user's project in their list...
        response = await client.get("api/v1/lothal/projects/", headers=logged_in_headers)
        assert foreign_id not in [p["id"] for p in response.json()]

        # ...and get/delete behave as if it doesn't exist (404, never 403).
        assert (
            await client.get(f"api/v1/lothal/projects/{foreign_id}", headers=logged_in_headers)
        ).status_code == status.HTTP_404_NOT_FOUND
        assert (
            await client.delete(f"api/v1/lothal/projects/{foreign_id}", headers=logged_in_headers)
        ).status_code == status.HTTP_404_NOT_FOUND
    finally:
        # Remove the seeded row before user_two's teardown deletes the user
        # (the FK has no ON DELETE CASCADE). Look up by the UUID primary key so
        # the match is type-exact.
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)
