"""Story A.1 — the `/api/v1/lothal/` surface exists as typed `501` stubs.

We assert the contract surface, not behaviour: every declared endpoint returns
the structured `501` when authenticated, returns `401`/`403` without a token,
and appears in the OpenAPI schema. Each endpoint gains behaviour tests when its
stub is replaced by a real implementation in a later story.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

# A non-existent project id is fine: the stubs short-circuit before any lookup.
PROJECT_ID = "00000000-0000-0000-0000-000000000000"

# (method, path, json body) for every endpoint in the contract. Bodies are valid
# so the only thing that can fail is auth (401) or the stub itself (501) — never
# request validation (422).
ENDPOINTS = [
    ("POST", "api/v1/lothal/projects/", {"name": "My App"}),
    ("GET", "api/v1/lothal/projects/", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("DELETE", f"api/v1/lothal/projects/{PROJECT_ID}", None),
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


@pytest.mark.parametrize(("method", "path", "json_body"), ENDPOINTS)
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


@pytest.mark.parametrize(("method", "path", "json_body"), ENDPOINTS)
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

    # Each stubbed route documents the structured 501 in its responses.
    assert "501" in paths["/api/v1/lothal/debug/llm"]["post"]["responses"]
