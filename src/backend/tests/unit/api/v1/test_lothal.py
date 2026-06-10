"""Lothal API tests.

Story A.1 declared the full `/api/v1/lothal/` surface as typed `501` stubs.
Story B.2 lights up the project CRUD (`POST`/`GET`/`GET {id}`/`DELETE` on
`/projects`) and Story 0.4 lights up `POST /debug/llm`, so those routes now
have behaviour tests; every other endpoint is still a stub and is asserted to
return the structured `501`.

Common to both: every endpoint requires auth and appears in the OpenAPI schema.
"""

from importlib.util import find_spec
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import lothal as lothal_api
from langflow.lothal.llm import LLMConfigError, LLMConnectionError
from langflow.services.database.models.lothal_project.model import CodeFile, Message, Project
from langflow.services.deps import session_scope
from sqlalchemy import inspect as sa_inspect
from sqlmodel import select

# A non-existent project id — used where a request must fail before reaching a
# handler (auth) or to prove project-scoped routes 404 for unknown projects.
PROJECT_ID = "00000000-0000-0000-0000-000000000000"

# (method, path template, json body) for the endpoints still backed by a `501`
# stub. Bodies are valid so a request can only fail on auth (401/403), the
# shared ownership check (404), or the stub itself (501) — never validation
# (422).
STUB_TEMPLATES = [
    ("POST", "api/v1/lothal/projects/{project_id}/chat", {"content": "hi"}),
    ("GET", "api/v1/lothal/projects/{project_id}/messages", None),
    ("GET", "api/v1/lothal/projects/{project_id}/prd", None),
    ("GET", "api/v1/lothal/projects/{project_id}/diagram", None),
    ("POST", "api/v1/lothal/projects/{project_id}/diagram/save", {"nodes": [], "edges": []}),
    ("POST", "api/v1/lothal/projects/{project_id}/diagram/approve", None),
    ("GET", "api/v1/lothal/projects/{project_id}/code", None),
    ("GET", "api/v1/lothal/projects/{project_id}/download", None),
]

# Every remaining stub is project-scoped, so each resolves ownership before
# stubbing.
PROJECT_SCOPED_STUB_TEMPLATES = [t for t in STUB_TEMPLATES if "{project_id}" in t[1]]

STUBBED_ENDPOINTS = [(m, p.format(project_id=PROJECT_ID), b) for m, p, b in STUB_TEMPLATES]

# The routes that have gone live: project CRUD (B.2) and the LLM debug
# round-trip (0.4). Still require auth, but no longer return `501`.
LIVE_ENDPOINTS = [
    ("POST", "api/v1/lothal/projects/", {"name": "My App"}),
    ("GET", "api/v1/lothal/projects/", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("DELETE", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("POST", "api/v1/lothal/debug/llm", {"message": "ping"}),
]

ALL_ENDPOINTS = LIVE_ENDPOINTS + STUBBED_ENDPOINTS


@pytest.mark.parametrize(("method", "path_template", "json_body"), STUB_TEMPLATES)
async def test_stub_returns_structured_501(
    client: AsyncClient,
    logged_in_headers: dict,
    method: str,
    path_template: str,
    json_body: dict | None,
):
    # Stubs only answer for an existing, owned project — the shared
    # `OwnedProject` dependency resolves ownership before the stub body runs.
    response = await client.post("api/v1/lothal/projects/", json={"name": "Stub"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    path = path_template.format(project_id=response.json()["id"])

    response = await client.request(method, path, json=json_body, headers=logged_in_headers)

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    body = response.json()
    assert body["status"] == "not_implemented"
    assert isinstance(body["detail"], str)
    assert body["detail"]


async def test_project_scoped_stubs_404_when_project_not_owned(client: AsyncClient, logged_in_headers: dict, user_two):
    # Ownership comes from the shared dependency, so every project-scoped stub
    # behaves like the live CRUD: a missing project and another user's project
    # are both an indistinguishable 404 — never a 501 that would confirm a
    # foreign project exists.
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id)
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        for project_id in (PROJECT_ID, str(foreign_pk)):
            for method, path_template, json_body in PROJECT_SCOPED_STUB_TEMPLATES:
                response = await client.request(
                    method,
                    path_template.format(project_id=project_id),
                    json=json_body,
                    headers=logged_in_headers,
                )
                assert response.status_code == status.HTTP_404_NOT_FOUND, (method, path_template, project_id)
    finally:
        # SQLite test DBs don't enforce the FK cascade, so clean up explicitly.
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


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

    # A still-stubbed route documents the structured 501 in its responses; the
    # live debug endpoint no longer advertises it.
    assert "501" in paths["/api/v1/lothal/projects/{project_id}/chat"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/debug/llm"]["post"]["responses"]


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


async def test_create_project_trims_name(client: AsyncClient, logged_in_headers: dict):
    # Surrounding whitespace is stripped before persisting — lock the contract.
    response = await client.post("api/v1/lothal/projects/", json={"name": "  My App  "}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "My App"


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
        # The user_id FK now cascades at the DB level, but SQLite test DBs
        # don't enforce FKs at all — clean the seeded row up explicitly so the
        # test leaves no orphans behind on any engine. Look up by the UUID
        # primary key so the match is type-exact.
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


async def test_delete_project_cascades_to_messages_and_code_files(client: AsyncClient, logged_in_headers: dict):
    # Create a project via the API, then seed child rows directly (the chat/code
    # endpoints that would create them are still 501 stubs).
    response = await client.post("api/v1/lothal/projects/", json={"name": "Cascade"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    project_pk = UUID(response.json()["id"])

    async with session_scope() as session:
        session.add(Message(project_id=project_pk, role="USER", content="hi", phase="CLARIFICATION"))
        session.add(CodeFile(project_id=project_pk, path="main.py", content="print('hi')\n"))

    # Delete via the API. The in-handler flush emits the cascade DELETEs (and
    # surfaces any error) in-request, before the 204 — exercising the async
    # cascade path with children present.
    response = await client.delete(f"api/v1/lothal/projects/{project_pk}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # The project and both child rows are gone.
    async with session_scope() as session:
        assert await session.get(Project, project_pk) is None
        messages = (await session.exec(select(Message).where(Message.project_id == project_pk))).all()
        code_files = (await session.exec(select(CodeFile).where(CodeFile.project_id == project_pk))).all()
        assert messages == []
        assert code_files == []


def test_message_requires_phase_at_construction():
    # SQLModel table models skip pydantic validation, so without the __init__
    # guard a missing phase only surfaces as an IntegrityError at flush time —
    # far from the bug. The guard fails at construction instead.
    with pytest.raises(TypeError, match="phase"):
        Message(project_id=uuid4(), role="USER", content="hi")
    with pytest.raises(TypeError, match="phase"):
        Message(project_id=uuid4(), role="USER", content="hi", phase=None)


async def test_lothal_fks_cascade_on_delete(client: AsyncClient):  # noqa: ARG001 — client boots the test DB
    # FK *enforcement* differs by engine (SQLite test DBs don't enforce FKs at
    # all), so pin the schema itself: every lothal FK must carry ON DELETE
    # CASCADE. Deleting a user must never be blocked by — or orphan — lothal
    # rows, and project deletes that bypass the ORM must still take messages
    # and code files with them.
    expected = {
        ("lothal_project", "user_id", "user"),
        ("lothal_message", "project_id", "lothal_project"),
        ("lothal_code_file", "project_id", "lothal_project"),
    }

    def _cascading_fks(sync_session) -> set[tuple[str, str, str]]:
        inspector = sa_inspect(sync_session.get_bind())
        found = set()
        for table, column, referred in expected:
            for fk in inspector.get_foreign_keys(table):
                if (
                    column in fk["constrained_columns"]
                    and fk["referred_table"] == referred
                    and (fk["options"].get("ondelete") or "").upper() == "CASCADE"
                ):
                    found.add((table, column, referred))
        return found

    async with session_scope() as session:
        found = await session.run_sync(_cascading_fks)

    assert found == expected


async def test_malformed_diagram_layout_reads_as_null(client: AsyncClient, logged_in_headers: dict):
    # One corrupted row must never 500 a project read — or, worse, the whole
    # list. Layouts are seeded straight into the DB: the save endpoint that
    # will write them (story 3.2) is still a stub.
    response = await client.post("api/v1/lothal/projects/", json={"name": "Layout"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    project_pk = UUID(response.json()["id"])

    cases = [
        ("not json", None),
        ("   ", None),
        ("[1, 2]", None),  # valid JSON but not an object
        ('{"n1": {"x": 1, "y": 2}}', {"n1": {"x": 1, "y": 2}}),
    ]
    for raw, expected in cases:
        async with session_scope() as session:
            project = await session.get(Project, project_pk)
            project.diagram_layout = raw

        response = await client.get(f"api/v1/lothal/projects/{project_pk}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["diagram_layout"] == expected

        response = await client.get("api/v1/lothal/projects/", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        listed = next(p for p in response.json() if p["id"] == str(project_pk))
        assert listed["diagram_layout"] == expected


# --- LLM debug (Story 0.4) ------------------------------------------------------

# `debug_llm` calls `call_llm` through its own module namespace, so the fakes
# below patch `langflow.api.v1.lothal.call_llm` — the bridge itself stays
# untouched and is covered by `tests/unit/lothal/test_llm_caller.py`.


async def test_debug_llm_returns_model_reply(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    captured = {}

    async def fake_call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return "pong"

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"response": "pong"}
    assert captured["messages"] == [{"role": "user", "content": "ping"}]


async def test_debug_llm_strips_whitespace_and_rejects_blank_message(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    async def fake_call_llm(messages, **_kwargs):
        return f"echo:{messages[0]['content']}"

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "  hi  "}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"response": "echo:hi"}

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "   "}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_debug_llm_maps_config_error_to_503(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    async def fake_call_llm(*_args, **_kwargs):
        msg = "the `claude-agent-sdk` package is required"
        raise LLMConfigError(msg)

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = response.json()["detail"]
    assert "LLM is not configured" in detail
    assert "claude-agent-sdk" in detail


async def test_debug_llm_maps_connection_error_to_502(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    async def fake_call_llm(*_args, **_kwargs):
        msg = "Claude returned an empty response."
        raise LLMConnectionError(msg)

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    detail = response.json()["detail"]
    assert "LLM call failed" in detail
    assert "empty response" in detail


@pytest.mark.api_key_required
async def test_debug_llm_real_subscription(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Story 0.4 acceptance: a real model reply comes back through the endpoint.

    Excluded from the default suite (`api_key_required`); run with a live
    Claude Code subscription via `-m api_key_required`. Pinned to Haiku — all
    real-LLM tests use `claude-haiku-4-5`.
    """
    if find_spec("claude_agent_sdk") is None:
        pytest.skip("claude-agent-sdk not installed")
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-haiku-4-5")

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "say hi"}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    reply = response.json()["response"]
    assert isinstance(reply, str)
    assert reply.strip()
