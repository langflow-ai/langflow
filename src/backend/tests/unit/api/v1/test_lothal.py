"""Lothal API tests.

Story A.1 declared the full `/api/v1/lothal/` surface as typed `501` stubs.
Story B.2 lights up the project CRUD (`POST`/`GET`/`GET {id}`/`DELETE` on
`/projects`) and Story 0.4 lights up `POST /debug/llm`, so those routes now
have behaviour tests; every other endpoint is still a stub and is asserted to
return the structured `501`.

Common to both: every endpoint requires auth and appears in the OpenAPI schema.
"""

import json
import shutil
from importlib.util import find_spec
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import lothal as lothal_api
from langflow.lothal.d2_compile import D2CompilerUnavailableError
from langflow.lothal.engines import architecture_generation, d2_gate, d2_validator
from langflow.lothal.engines import clarification as clarification_engine
from langflow.lothal.llm import LLMConfigError, LLMConnectionError
from langflow.services.database.models.lothal_project.model import (
    CodeFile,
    Message,
    PMProjectLink,
    Project,
    PrototypeArtifact,
    PrototypeStatus,
)
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
    ("GET", "api/v1/lothal/projects/{project_id}/code", None),
    ("GET", "api/v1/lothal/projects/{project_id}/download", None),
    # The prototype surface went live in U.4-U.7 (was stubbed in U.0); it now lives
    # in LIVE_ENDPOINTS with behaviour tests further down.
]

# Every remaining stub is project-scoped, so each resolves ownership before
# stubbing.
PROJECT_SCOPED_STUB_TEMPLATES = [t for t in STUB_TEMPLATES if "{project_id}" in t[1]]

STUBBED_ENDPOINTS = [(m, p.format(project_id=PROJECT_ID), b) for m, p, b in STUB_TEMPLATES]

# The routes that have gone live: project CRUD (B.2), the LLM debug round-trip
# (0.4), chat routing + message history (1.2), the PRD read (1.3), the diagram
# read (2.3), and diagram approve (D.11). Still require auth, but no longer
# return `501`. (POST /diagram/save was retired in D.9 — the route no longer
# exists; `test_diagram_save_route_is_gone` pins its removal.)
LIVE_ENDPOINTS = [
    ("POST", "api/v1/lothal/projects/", {"name": "My App"}),
    ("GET", "api/v1/lothal/projects/", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("DELETE", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/chat", {"content": "hi"}),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/messages", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/prd", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/diagram", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/diagram/approve", None),
    # Prototype stage (Epic UI, Stories U.4-U.7) — live backends driving Open Design.
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/prototype", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/prototype/generate", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/prototype/refine", {"content": "make it blue"}),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/prototype/approve", None),
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
        "/api/v1/lothal/projects/{project_id}/diagram/approve",
        "/api/v1/lothal/projects/{project_id}/prototype",
        "/api/v1/lothal/projects/{project_id}/prototype/generate",
        "/api/v1/lothal/projects/{project_id}/prototype/refine",
        "/api/v1/lothal/projects/{project_id}/prototype/approve",
        "/api/v1/lothal/projects/{project_id}/code",
        "/api/v1/lothal/projects/{project_id}/download",
        "/api/v1/lothal/debug/llm",
    }
    assert expected <= set(paths)

    # D.9 retired the canvas-save endpoint: it must no longer appear in the surface.
    assert "/api/v1/lothal/projects/{project_id}/diagram/save" not in paths

    # A still-stubbed route documents the structured 501 in its responses; the
    # routes that have gone live (chat, debug, prd, diagram, approve, prototype)
    # no longer advertise it.
    assert "501" in paths["/api/v1/lothal/projects/{project_id}/code"]["get"]["responses"]
    assert "501" in paths["/api/v1/lothal/projects/{project_id}/download"]["get"]["responses"]
    # The prototype surface went live in U.4-U.7 — no route advertises the 501 now.
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/prototype"]["get"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/prototype/generate"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/prototype/refine"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/prototype/approve"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/diagram"]["get"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/diagram/approve"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/chat"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/prd"]["get"]["responses"]
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
    assert project["diagram_json"] is None
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


async def test_project_round_trips_diagram_d2(client: AsyncClient, logged_in_headers: dict):
    # D2 source is the Epic D diagram artifact, persisted to the new nullable
    # `diagram_d2` column. Create via the API (null by default), write D2 through
    # the ORM, and confirm it survives a reload with the legacy `diagram_json`
    # column left untouched alongside it.
    response = await client.post("api/v1/lothal/projects/", json={"name": "D2 Roundtrip"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    project_pk = UUID(response.json()["id"])

    d2_source = "direction: right\nclient -> api: request\napi -> db: query"
    async with session_scope() as session:
        created = await session.get(Project, project_pk)
        assert created.diagram_d2 is None  # a fresh project has no D2 yet
        created.diagram_d2 = d2_source
        session.add(created)

    async with session_scope() as session:
        reloaded = await session.get(Project, project_pk)
        assert reloaded.diagram_d2 == d2_source
        assert reloaded.diagram_json is None  # legacy column untouched by the D2 write
        await session.delete(reloaded)


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


async def test_malformed_diagram_json_reads_as_null(client: AsyncClient, logged_in_headers: dict):
    # One corrupted row must never 500 a project read — or, worse, the whole
    # list. The legacy `diagram_json` column survives the D2 migration for
    # existing data (D.13 converts it to `diagram_d2`; the column drop is a later
    # migration), so its read-boundary parsing still has to tolerate junk. Seeded
    # straight into the DB — nothing writes `diagram_json` any more.
    response = await client.post("api/v1/lothal/projects/", json={"name": "Graph"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    project_pk = UUID(response.json()["id"])

    cases = [
        ("not json", None),
        ("   ", None),
        ("[1, 2]", None),  # valid JSON but not an object
        ('{"nodes": [], "edges": []}', {"nodes": [], "edges": []}),
    ]
    for raw, expected in cases:
        async with session_scope() as session:
            project = await session.get(Project, project_pk)
            project.diagram_json = raw

        response = await client.get(f"api/v1/lothal/projects/{project_pk}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["diagram_json"] == expected

        response = await client.get("api/v1/lothal/projects/", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        listed = next(p for p in response.json() if p["id"] == str(project_pk))
        assert listed["diagram_json"] == expected


# --- LLM debug (Story 0.4) ------------------------------------------------------

# `debug_llm` calls `call_llm` through its own module namespace, so the fakes
# below patch `langflow.api.v1.lothal.call_llm` — the bridge itself stays
# untouched and is covered by `tests/unit/lothal/test_llm_caller.py`.
#
# The endpoint triggers a real, billable model call, so it is superuser-gated:
# the happy-path tests authenticate as a superuser (`logged_in_headers_super_user`)
# and `test_debug_llm_forbidden_for_non_superuser` locks the gate in.


async def test_debug_llm_forbidden_for_non_superuser(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """An ordinary authenticated user must not be able to drive LLM calls."""
    called = False

    async def fake_call_llm(*_args, **_kwargs):
        nonlocal called
        called = True
        return "should not reach here"

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post("api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert called is False  # the gate runs before the handler body


async def test_debug_llm_returns_model_reply(client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch):
    captured = {}

    async def fake_call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return "pong"

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers_super_user
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"response": "pong"}
    assert captured["messages"] == [{"role": "user", "content": "ping"}]


async def test_debug_llm_strips_whitespace_and_rejects_blank_message(
    client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch
):
    async def fake_call_llm(messages, **_kwargs):
        return f"echo:{messages[0]['content']}"

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "  hi  "}, headers=logged_in_headers_super_user
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"response": "echo:hi"}

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "   "}, headers=logged_in_headers_super_user
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_debug_llm_maps_config_error_to_503(client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch):
    async def fake_call_llm(*_args, **_kwargs):
        msg = "the `claude-agent-sdk` package is required"
        raise LLMConfigError(msg)

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers_super_user
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = response.json()["detail"]
    assert "LLM is not configured" in detail
    assert "claude-agent-sdk" in detail


async def test_debug_llm_maps_connection_error_to_502(
    client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch
):
    async def fake_call_llm(*_args, **_kwargs):
        msg = "Claude returned an empty response."
        raise LLMConnectionError(msg)

    monkeypatch.setattr(lothal_api, "call_llm", fake_call_llm)

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "ping"}, headers=logged_in_headers_super_user
    )

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    detail = response.json()["detail"]
    assert "LLM call failed" in detail
    assert "empty response" in detail


# --- ORM update bumps updated_at (Task 1 regression) ----------------------------


async def test_project_updated_at_bumped_on_orm_update(client: AsyncClient, active_user):  # noqa: ARG001 — client boots DB
    """updated_at must advance when a field is mutated and the row flushed.

    Uses session_scope directly (no HTTP round-trip) so the onupdate fires
    through the ORM UPDATE path, which is what the Column(onupdate=...) hooks.
    """
    async with session_scope() as session:
        project = Project(name="bump-test", user_id=active_user.id)
        session.add(project)
        await session.flush()
        await session.refresh(project)
        pk = project.id
        created_at = project.created_at
        updated_at_before = project.updated_at

    # Mutate in a new session so that the ORM issues a genuine UPDATE statement.
    async with session_scope() as session:
        project = await session.get(Project, pk)
        assert project is not None
        project.name = "bump-test-renamed"
        await session.flush()
        await session.refresh(project)
        updated_at_after = project.updated_at

    assert updated_at_after >= created_at, "updated_at must not go before created_at"
    assert updated_at_after > updated_at_before, "updated_at must advance after a mutation"

    # Cleanup
    async with session_scope() as session:
        leftover = await session.get(Project, pk)
        if leftover:
            await session.delete(leftover)


# --- Message suggestions round-trip (Task 5b) ------------------------------------


async def test_message_suggestions_round_trip(client: AsyncClient, active_user):  # noqa: ARG001 — client boots DB
    """Suggestions are persisted and survive a DB round-trip via the ORM.

    Covers both a non-empty list (ASSISTANT clarification chips) and the []
    default for USER messages, and asserts >= created_at for the created_at
    column while we're here.
    """
    async with session_scope() as session:
        project = Project(name="suggestions-test", user_id=active_user.id)
        session.add(project)
        await session.flush()
        project_pk = project.id

        assistant_msg = Message(
            project_id=project_pk,
            role="ASSISTANT",
            content="Which framework?",
            suggestions=["React", "Vue", "Svelte"],
            phase="CLARIFICATION",
        )
        user_msg = Message(
            project_id=project_pk,
            role="USER",
            content="React please",
            phase="CLARIFICATION",
        )
        session.add(assistant_msg)
        session.add(user_msg)
        await session.flush()
        assistant_pk = assistant_msg.id
        user_pk = user_msg.id

    # Read back in a fresh session to verify persistence.
    async with session_scope() as session:
        loaded_assistant = await session.get(Message, assistant_pk)
        loaded_user = await session.get(Message, user_pk)

        assert loaded_assistant is not None
        assert loaded_assistant.suggestions == ["React", "Vue", "Svelte"]
        assert loaded_assistant.created_at is not None

        assert loaded_user is not None
        assert loaded_user.suggestions == [], "USER message with default suggestions must be []"

    # Cleanup — project cascade removes messages.
    async with session_scope() as session:
        leftover = await session.get(Project, project_pk)
        if leftover:
            await session.delete(leftover)


# --- Chat routing + suggestions persistence (Story 1.2) -------------------------

# Chat drives the *real* clarification engine end to end; only the model call is
# faked. The engine reads `call_llm` from its own module, so these tests patch
# `langflow.lothal.engines.clarification.call_llm` — `process_turn`, the phase
# router, parsing, and the persistence path all run for real.


def _clarification_reply(question: str, suggestions: list[str]) -> str:
    """The JSON-object shape the clarification engine expects each turn."""
    return json.dumps({"message": question, "suggestions": suggestions})


async def _create_chat_project(client: AsyncClient, headers: dict, name: str = "Chat") -> str:
    response = await client.post("api/v1/lothal/projects/", json={"name": name}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


async def test_chat_persists_turn_and_replays_suggestions(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """A no-signal turn stores both messages, returns the reply with chips, and replays them.

    The phase stays put; `GET /messages` rehydrates the user turn (no chips) and the
    assistant turn (chips) in order.
    """
    project_id = await _create_chat_project(client, logged_in_headers)

    async def fake_call_llm(_messages, **_kwargs):
        return _clarification_reply("Who is it for?", ["Just me", "My team"])

    monkeypatch.setattr(clarification_engine, "call_llm", fake_call_llm)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "a todo app"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["role"] == "ASSISTANT"
    assert reply["content"] == "Who is it for?"
    assert reply["suggestions"] == ["Just me", "My team"]
    assert reply["phase"] == "CLARIFICATION"

    # History replays user turn (no chips) then assistant turn (chips), oldest first.
    response = await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    messages = response.json()
    assert [m["role"] for m in messages] == ["USER", "ASSISTANT"]
    assert messages[0]["content"] == "a todo app"
    assert messages[0]["suggestions"] == []
    assert messages[1]["suggestions"] == ["Just me", "My team"]
    assert all(m["phase"] == "CLARIFICATION" for m in messages)

    # A no-signal turn doesn't move the project or write a PRD.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "CLARIFICATION"
    assert project["prd_content"] is None


async def test_no_signal_chat_turn_bumps_updated_at_and_reorders_list(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """A no-signal clarification turn advances updated_at and reorders the list.

    Regression for the audit finding that a turn changing neither the diagram nor
    the phase left the project row untouched — freezing updated_at so an
    actively-chatted project sank below idle ones in the updated_at-DESC list.
    """
    older = await _create_chat_project(client, logged_in_headers, name="Older")
    newer = await _create_chat_project(client, logged_in_headers, name="Newer")

    async def list_ids() -> list[str]:
        resp = await client.get("api/v1/lothal/projects/", headers=logged_in_headers)
        return [p["id"] for p in resp.json()]

    # Freshly created: the newer project leads the updated_at-DESC list.
    ids = await list_ids()
    assert ids.index(newer) < ids.index(older)
    before = (await client.get(f"api/v1/lothal/projects/{older}", headers=logged_in_headers)).json()["updated_at"]

    async def fake_call_llm(_messages, **_kwargs):
        return _clarification_reply("Who is it for?", ["Me", "Team"])

    monkeypatch.setattr(clarification_engine, "call_llm", fake_call_llm)

    # A no-signal clarification turn in the older project (phase stays put).
    response = await client.post(
        f"api/v1/lothal/projects/{older}/chat", json={"content": "a todo app"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["phase"] == "CLARIFICATION"

    after = (await client.get(f"api/v1/lothal/projects/{older}", headers=logged_in_headers)).json()["updated_at"]
    assert after > before, "a no-signal chat turn must advance updated_at"

    # The chatted project now leads the list ahead of the idle newer one.
    ids = await list_ids()
    assert ids.index(older) < ids.index(newer)


async def test_chat_three_no_signal_turns_then_clarity_transition(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Backlog acceptance for the clarification turn lifecycle (phase-gates).

    Three no-signal turns yield 6 messages with the phase unchanged; one
    `[CLARITY_REACHED]` turn DRAFTS the PRD (token stripped, stored on
    `prd_content`) but HOLDS in CLARIFICATION — leaving is now an explicit
    `POST /prd/approve`, and the chat reply is a short handoff, not the PRD.
    """
    project_id = await _create_chat_project(client, logged_in_headers)

    replies = iter(
        [
            _clarification_reply("Q1?", ["a", "b"]),
            _clarification_reply("Q2?", ["c", "d"]),
            _clarification_reply("Q3?", ["e", "f"]),
            "[CLARITY_REACHED]\n## Overview\nA todo app for individuals.",
        ]
    )

    async def fake_call_llm(_messages, **_kwargs):
        return next(replies)

    monkeypatch.setattr(clarification_engine, "call_llm", fake_call_llm)

    # Three no-signal turns keep the project in CLARIFICATION.
    for turn in range(3):
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/chat", json={"content": f"turn {turn}"}, headers=logged_in_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["phase"] == "CLARIFICATION"

    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert len(messages) == 6  # 3 turns x (user + assistant)
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "CLARIFICATION"
    assert project["prd_content"] is None

    # The clarity turn drafts the PRD and HOLDS in CLARIFICATION (no auto-advance).
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "looks good"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["phase"] == "CLARIFICATION"  # the turn ran under CLARIFICATION
    assert reply["suggestions"] == []
    assert "[CLARITY_REACHED]" not in reply["content"]  # control token stripped
    assert "Overview" not in reply["content"]  # the chat reply is a handoff, not the PRD

    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "CLARIFICATION"  # holds — leaving is an explicit approve
    assert project["prd_content"] is not None
    assert "[CLARITY_REACHED]" not in project["prd_content"]
    assert "Overview" in project["prd_content"]  # the PRD landed on the main page


# --- Diagram generation (Story 2.1, re-pointed to D2 in Epic D.2) -------------


def _diagram_reply() -> str:
    """A D2 sequence diagram in the shape the generator now emits (Epic D.2)."""
    return "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok\nuser -> api: poll"


async def test_architecture_generation_turn_persists_artifact_map_and_stays_in_architecture(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Backlog acceptance for Epic E.3 generation (fake LLM).

    The first ARCHITECTURE turn (no artifact map yet) runs the architecture engine
    for real (only the model calls are faked): it persists the full artifact map
    (`adr.md` + four `diagrams/*.d2`) to `lothal_project.artifacts`, mirrors the
    sequence diagram onto `diagram_d2` so the single-diagram read/approve flow
    keeps working, leaves the legacy `diagram_json` null, and — no auto-advance —
    stays in ARCHITECTURE so the next turn refines the set. The reply is stamped
    with the phase the turn ran under (ARCHITECTURE).
    """
    project_id = await _create_chat_project(client, logged_in_headers)

    # Precondition: the project has left CLARIFICATION (PRD written, phase moved).
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        session.add(project)

    async def fake_diagram_llm(_messages, **_kwargs):
        return _diagram_reply()

    async def fake_adr_llm(_messages, **_kwargs):
        return "# Architecture Decision Record\n\n## Context\nA todo app."

    monkeypatch.setattr(d2_gate, "call_llm", fake_diagram_llm)
    monkeypatch.setattr(architecture_generation, "call_llm", fake_adr_llm)
    monkeypatch.setattr(d2_validator, "call_llm", _stub_validator_reply("VALID"))

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "design the architecture"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["role"] == "ASSISTANT"
    assert reply["phase"] == "ARCHITECTURE"  # the turn ran under this phase
    assert reply["suggestions"] == []
    assert "4 diagrams" in reply["content"]  # text grounded in the generated set

    # The full artifact map lands in `artifacts`; the sequence diagram mirrors onto
    # `diagram_d2`; the legacy `diagram_json` stays null; the project stays in
    # ARCHITECTURE (no auto-advance) so the next turn refines the set.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "ARCHITECTURE"
    assert project["diagram_json"] is None
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert set(stored.artifacts) == {
            "adr.md",
            "diagrams/context.d2",
            "diagrams/container.d2",
            "diagrams/data-model.d2",
            "diagrams/sequence.d2",
        }
        assert stored.artifacts["diagrams/sequence.d2"] == _diagram_reply()
        assert stored.diagram_d2 == _diagram_reply()


async def test_architecture_generation_empty_reply_is_502_and_rolls_back(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """An empty D2 reply fails the generation turn as a bad model round-trip and persists nothing.

    The whole turn is one transaction, so the user message is rolled back too and
    `artifacts`/`diagram_d2` stay null — the user can resend cleanly. (The ADR
    round-trip is faked valid here so the failure is unambiguously the empty
    diagram; compile-validation with a corrective retry is Epic D.3.)
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        session.add(project)

    async def fake_diagram_llm(_messages, **_kwargs):
        return "   \n  "  # empty after fences/whitespace are stripped

    async def fake_adr_llm(_messages, **_kwargs):
        return "# ADR\n\n## Context\nA todo app."

    monkeypatch.setattr(d2_gate, "call_llm", fake_diagram_llm)
    monkeypatch.setattr(architecture_generation, "call_llm", fake_adr_llm)
    monkeypatch.setattr(d2_validator, "call_llm", _stub_validator_reply("VALID"))

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "design the architecture"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY

    # Nothing persisted: no artifacts, no diagram, and the user turn rolled back with it.
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.artifacts is None
        assert stored.diagram_d2 is None
        assert stored.diagram_json is None
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert messages == []


# --- Diagram refinement (Epic D.8) --------------------------------------------


def _refined_d2() -> str:
    """The updated D2 a refinement turn's (faked) model returns."""
    return "shape: sequence_diagram\nbrowser: Browser\napi: API\n\nbrowser -> api: submit\napi -> browser: ok"


def _seed_artifacts(sequence_d2: str) -> dict[str, str]:
    """A full architecture artifact map; `diagrams/sequence.d2` is the refine default target."""
    return {
        "adr.md": "# Architecture Decision Record\n\n## Context\nA todo app.",
        "diagrams/context.d2": "direction: right\nuser: End User {shape: person}\napp: App\nuser -> app: uses",
        "diagrams/container.d2": "direction: right\nsystem: App {\n  api: API\n}",
        "diagrams/data-model.d2": "users: {\n  shape: sql_table\n  id: int\n}",
        "diagrams/sequence.d2": sequence_d2,
    }


async def test_refinement_turn_updates_d2_and_holds_phase(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Backlog acceptance for Epic D.8 refinement carried into the E.3 artifact map (fake LLM).

    A chat turn while the project already has an artifact map runs the refinement
    engine for real (only the model call is faked): with no explicit target it
    edits the sequence diagram (what the single-diagram canvas shows). The turn the
    model receives carries that diagram's current D2, the PRD, and the anchored
    element id; the updated D2 is written back into `artifacts["diagrams/sequence.d2"]`
    and mirrored onto `diagram_d2`, `GET /diagram` reflects it, and the project
    stays in ARCHITECTURE (approval is D.11).
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    seed_d2 = "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.prd_content = "## Overview\nA todo app for individuals."
        project.artifacts = _seed_artifacts(seed_d2)
        project.diagram_d2 = seed_d2
        session.add(project)

    captured: dict = {}

    async def fake_call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return _refined_d2()

    monkeypatch.setattr(d2_gate, "call_llm", fake_call_llm)
    # The refinement engine also runs the D.10 coherence validator (its own
    # call_llm seam); a coherent edit returns VALID and adds no extra message.
    monkeypatch.setattr(d2_validator, "call_llm", _stub_validator_reply("VALID"))

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "rename `user` to Browser"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["role"] == "ASSISTANT"
    assert reply["phase"] == "ARCHITECTURE"
    assert reply["suggestions"] == []

    # The refinement turn the model saw carried the current sequence D2, the PRD,
    # and the anchored element id (the D.7 composer serialises it backtick-wrapped).
    composed = captured["messages"][-1]["content"]
    assert "user -> api: submit" in composed  # the current diagram to edit
    assert "A todo app for individuals." in composed  # the PRD
    assert "`user`" in composed  # the referenced element id

    # The updated D2 is written back into the map and mirrored onto `diagram_d2`;
    # GET /diagram reflects it; the phase holds.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "ARCHITECTURE"
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.artifacts["diagrams/sequence.d2"] == _refined_d2()
        assert stored.diagram_d2 == _refined_d2()

    diagram = (await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)).json()
    assert diagram["d2"] == _refined_d2()

    # A coherent edit adds no extra warning message — just the user + reply turns.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert [m["role"] for m in messages] == ["USER", "ASSISTANT"]


def _stub_validator_reply(reply: str):
    """An async `call_llm` stub for the D.10 validator that returns a fixed reply."""

    async def _call_llm(_messages, **_kwargs):
        return reply

    return _call_llm


async def test_refinement_contradiction_surfaces_as_warning_message(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Backlog acceptance for Epic D.10 (fake LLM): a coherence WARNING becomes an ASSISTANT message.

    The refinement engine compiles the edit (D.3) then validates it against the
    PRD (D.10). When the validator flags a contradiction, the chat endpoint stores
    the warning as its own ASSISTANT turn — so `/messages` shows the reply *and*
    the warning. A `VALID` verdict (covered above) adds no message.
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    seed_d2 = "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.prd_content = "## Overview\nA todo app that must persist tasks in a database."
        project.artifacts = _seed_artifacts(seed_d2)
        project.diagram_d2 = seed_d2
        session.add(project)

    monkeypatch.setattr(d2_gate, "call_llm", _stub_validator_reply(_refined_d2()))
    monkeypatch.setattr(
        d2_validator, "call_llm", _stub_validator_reply("WARNING: the diagram no longer writes to the database")
    )

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "drop the database"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    # /messages carries the user turn, the assistant reply, then the warning, in order.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert [m["role"] for m in messages] == ["USER", "ASSISTANT", "ASSISTANT"]
    warning = messages[-1]
    assert "no longer writes to the database" in warning["content"]
    assert warning["phase"] == "ARCHITECTURE"
    # The edit still landed despite the warning (advisory, not a gate).
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.diagram_d2 == _refined_d2()


async def test_refine_unknown_artifact_target_is_422_and_no_op(client: AsyncClient, logged_in_headers: dict):
    """An explicit `artifact` not in the map is rejected up front (422) and records no turn.

    Epic E.3: a refine turn names the artifact it edits. A stale/mistyped target
    must never silently retarget a different artifact — the endpoint 422s before
    any work, so the conversation and artifact map are untouched.
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    seed_d2 = "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.artifacts = _seed_artifacts(seed_d2)
        session.add(project)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "edit it", "artifact": "diagrams/does-not-exist.d2"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # No turn recorded — the guard runs before any message is stored.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert messages == []


# --- Diagram approve (Epic D.11) ----------------------------------------------


async def test_diagram_save_route_is_gone(client: AsyncClient, logged_in_headers: dict):
    """D.9: the canvas-save endpoint was retired — POSTing to it is a 404, not a 501."""
    project_id = await _create_chat_project(client, logged_in_headers)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/diagram/save",
        json={"nodes": [], "edges": []},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_approve_in_architecture_advances_to_prototype_and_keeps_d2(client: AsyncClient, logged_in_headers: dict):
    """Acceptance for Epic UI U.0: approve ARCHITECTURE → PROTOTYPE (was CODE_GENERATION), D2 retained."""
    project_id = await _create_chat_project(client, logged_in_headers)
    seed_d2 = "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.diagram_d2 = seed_d2
        session.add(project)

    response = await client.post(f"api/v1/lothal/projects/{project_id}/diagram/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"phase": "PROTOTYPE"}

    # The phase advanced and the approved D2 is retained verbatim; /diagram still serves it in PROTOTYPE.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "PROTOTYPE"
    diagram = (await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)).json()
    assert diagram["d2"] == seed_d2


@pytest.mark.parametrize("phase", ["CLARIFICATION", "PROTOTYPE", "PLAN", "CODE_GENERATION", "DONE"])
async def test_approve_rejected_outside_architecture(client: AsyncClient, logged_in_headers: dict, phase: str):
    """Approve is only valid in ARCHITECTURE; any other phase (incl. the new PROTOTYPE) is a 409 and a no-op."""
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        session.add(project)

    response = await client.post(f"api/v1/lothal/projects/{project_id}/diagram/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT

    # The phase is unchanged — a rejected approve never advances the project.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == phase


# --- PRD edit + approve (phase-gates) ----------------------------------------


async def test_prd_edit_updates_the_drafted_spec(client: AsyncClient, logged_in_headers: dict):
    """PATCH /prd saves a direct edit while in CLARIFICATION with a drafted PRD."""
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.prd_content = "# Spec\n\nOld body."
        session.add(project)

    response = await client.patch(
        f"api/v1/lothal/projects/{project_id}/prd",
        json={"content": "# Spec\n\nNew body."},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["content"] == "# Spec\n\nNew body."

    prd = (await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)).json()
    assert prd["content"] == "# Spec\n\nNew body."


async def test_prd_edit_rejects_blank(client: AsyncClient, logged_in_headers: dict):
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.prd_content = "# Spec\n\nBody."
        session.add(project)
    response = await client.patch(
        f"api/v1/lothal/projects/{project_id}/prd", json={"content": "   "}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PROTOTYPE", "PLAN"])
async def test_prd_edit_rejected_outside_clarification(client: AsyncClient, logged_in_headers: dict, phase: str):
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        project.prd_content = "# Spec\n\nBody."
        session.add(project)
    response = await client.patch(
        f"api/v1/lothal/projects/{project_id}/prd", json={"content": "edited"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_prd_approve_advances_to_architecture(client: AsyncClient, logged_in_headers: dict):
    """Approving the drafted PRD advances CLARIFICATION → ARCHITECTURE."""
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.prd_content = "# Spec\n\nA todo app."
        session.add(project)

    response = await client.post(f"api/v1/lothal/projects/{project_id}/prd/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"phase": "ARCHITECTURE"}

    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "ARCHITECTURE"


async def test_prd_approve_rejected_without_a_prd(client: AsyncClient, logged_in_headers: dict):
    project_id = await _create_chat_project(client, logged_in_headers)  # CLARIFICATION, no PRD yet
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prd/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "CLARIFICATION"


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PROTOTYPE", "PLAN", "CODE_GENERATION", "DONE"])
async def test_prd_approve_rejected_outside_clarification(client: AsyncClient, logged_in_headers: dict, phase: str):
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        project.prd_content = "# Spec\n\nBody."
        session.add(project)
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prd/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT


# --- Architecture generate on entry (phase-gates) ----------------------------


async def test_architecture_generate_populates_the_artifact_map(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """POST /architecture/generate runs the ADR + diagram batch on an empty map."""
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.prd_content = "# Spec\n\nA todo app."
        session.add(project)

    async def fake_diagram_llm(_messages, **_kwargs):
        return _diagram_reply()

    async def fake_adr_llm(_messages, **_kwargs):
        return "# Architecture Decision Record\n\n## Context\nA todo app."

    monkeypatch.setattr(d2_gate, "call_llm", fake_diagram_llm)
    monkeypatch.setattr(architecture_generation, "call_llm", fake_adr_llm)
    monkeypatch.setattr(d2_validator, "call_llm", _stub_validator_reply("VALID"))

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/architecture/generate", headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["role"] == "ASSISTANT"

    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert set(stored.artifacts) == {
            "adr.md",
            "diagrams/context.d2",
            "diagrams/container.d2",
            "diagrams/data-model.d2",
            "diagrams/sequence.d2",
        }
        assert stored.diagram_d2 == _diagram_reply()


async def test_architecture_generate_rejected_without_a_prd(client: AsyncClient, logged_in_headers: dict):
    """Never design an architecture from nothing — a missing PRD is a 409."""
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"  # reached without a PRD (defensive guard)
        session.add(project)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/architecture/generate", headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_architecture_generate_rejected_when_already_generated(client: AsyncClient, logged_in_headers: dict):
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.artifacts = {"adr.md": "# ADR"}
        session.add(project)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/architecture/generate", headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize("phase", ["CLARIFICATION", "PROTOTYPE", "PLAN"])
async def test_architecture_generate_rejected_outside_architecture(
    client: AsyncClient, logged_in_headers: dict, phase: str
):
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        session.add(project)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/architecture/generate", headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_approve_unowned_project_is_404(client: AsyncClient, logged_in_headers: dict, user_two):
    """Ownership is checked first: approving another user's project 404s, never 409/200."""
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id, phase="ARCHITECTURE")
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        response = await client.post(f"api/v1/lothal/projects/{foreign_pk}/diagram/approve", headers=logged_in_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


@pytest.mark.parametrize("diagram_d2", [None, "   \n  "])
async def test_approve_with_no_diagram_is_409(client: AsyncClient, logged_in_headers: dict, diagram_d2):
    """Approve guards against advancing to CODE_GENERATION with no diagram to hand code-gen.

    Covers both an absent diagram (`None`, e.g. a legacy project) and a blank /
    whitespace-only one — the handler rejects both via its `.strip()` check.
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.diagram_d2 = diagram_d2
        session.add(project)

    response = await client.post(f"api/v1/lothal/projects/{project_id}/diagram/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT

    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "ARCHITECTURE"  # not advanced


@pytest.mark.parametrize("phase", ["PROTOTYPE", "PLAN", "CODE_GENERATION", "DONE"])
async def test_chat_in_engineless_phase_is_clean_409_not_500(client: AsyncClient, logged_in_headers: dict, phase: str):
    """Chatting in an engineless phase (PROTOTYPE/CODE_GENERATION/DONE, reachable via approve) is a 409, not a 500.

    Regression: `process_turn` raises a plain ValueError for an unregistered phase;
    without the guard the chat endpoint's `except (LLMConfigError, LLMConnectionError)`
    misses it → 500 that leaks the engine registry and 500s on every retry.
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        session.add(project)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "hello?"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    # No turn was recorded — the guard runs before any message is stored.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert messages == []


# --- PRD endpoint (Story 1.3) -------------------------------------------------


async def test_prd_is_null_before_clarity_and_content_after(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Backlog acceptance for `GET /prd`: `null` until the project leaves CLARIFICATION, populated after.

    Drives the real clarification turn lifecycle (only the model call is faked):
    a no-signal turn keeps the PRD `null`; a `[CLARITY_REACHED]` turn transitions
    the project and `GET /prd` returns the stored summary with the token stripped.
    """
    project_id = await _create_chat_project(client, logged_in_headers)

    # No turns yet → PRD is null.
    response = await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"content": None}

    replies = iter(
        [
            _clarification_reply("Who is it for?", ["Just me", "My team"]),
            "[CLARITY_REACHED]\n## Overview\nA todo app for individuals.",
        ]
    )

    async def fake_call_llm(_messages, **_kwargs):
        return next(replies)

    monkeypatch.setattr(clarification_engine, "call_llm", fake_call_llm)

    # A no-signal turn keeps the project in CLARIFICATION → PRD still null.
    await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "a todo app"}, headers=logged_in_headers
    )
    response = await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"content": None}

    # The clarity turn transitions the project → PRD is the stored summary.
    await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "looks good"}, headers=logged_in_headers
    )
    response = await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    content = response.json()["content"]
    assert content is not None
    assert "[CLARITY_REACHED]" not in content  # control token stripped
    assert "Overview" in content


async def test_prd_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """The PRD read is behind the shared ownership check — another user's project 404s."""
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id)
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        for project_id in (PROJECT_ID, str(foreign_pk)):
            response = await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND, project_id
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


# --- Diagram endpoint (Epic D.4, supersedes Story 2.3) ------------------------

# The diagram artifact is D2 source now, not an xyflow graph. This is the shape
# the generator emits (Epic D.2) and the chat endpoint persists verbatim to
# `lothal_project.diagram_d2`. Seeded straight into the column here — the read
# never compiles or validates it.
_SEED_D2 = (
    "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: request\napi -> user: response\nuser -> api: ack"
)


async def _set_phase_and_d2(project_pk: UUID, *, phase: str, diagram_d2: str | None) -> None:
    """Seed a project's phase and raw `diagram_d2` source directly (no live writer yet)."""
    async with session_scope() as session:
        project = await session.get(Project, project_pk)
        project.phase = phase
        project.diagram_d2 = diagram_d2


_STUB_SVG = "<svg data-stub='diagram'></svg>"


@pytest.fixture
def stub_diagram_render(monkeypatch):
    """Make GET /diagram's server-side SVG render deterministic, regardless of `d2`.

    The endpoint renders stored D2 to SVG via the `d2` binary (D.6). These read
    tests assert the d2/phase/ownership contract, not the compiler, so we stub the
    render to a fixed SVG so they pass identically whether or not `d2` is installed
    in the test environment. The real compile→SVG path is covered by the gated
    `test_diagram_server_renders_svg_real` below and in `test_d2_compile.py`.
    """
    from langflow.lothal.d2_compile import D2RenderResult

    async def _render(_src: str) -> D2RenderResult:
        return D2RenderResult(svg=_STUB_SVG)

    monkeypatch.setattr(lothal_api, "render_d2", _render)
    return _STUB_SVG


async def test_diagram_403_in_clarification(client: AsyncClient, logged_in_headers: dict):
    """A fresh project sits in CLARIFICATION, before any diagram exists → 403."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_diagram_empty_before_generation_completes(client: AsyncClient, logged_in_headers: dict):
    """Past CLARIFICATION but before the generator emits → empty payload (`d2: null`), not 500."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=None)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": None, "svg": None}


async def test_diagram_returns_seeded_d2(client: AsyncClient, logged_in_headers: dict, stub_diagram_render):
    """A seeded `diagram_d2` comes back as the D2 source verbatim plus the rendered SVG."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=_SEED_D2)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    # The D2 shape: source text plus the server-rendered SVG (D.6) — no xyflow
    # `nodes`/`edges`.
    assert set(body) == {"d2", "svg"}
    assert body["d2"] == _SEED_D2
    assert body["svg"] == stub_diagram_render


async def test_diagram_readable_in_later_phases(client: AsyncClient, logged_in_headers: dict):
    """The D2 source stays readable through the prototype stage, code generation, and done."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    for phase in ("ARCHITECTURE", "PROTOTYPE", "CODE_GENERATION", "DONE"):
        await _set_phase_and_d2(UUID(project_id), phase=phase, diagram_d2=_SEED_D2)
        response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK, phase
        assert response.json()["d2"] == _SEED_D2, phase


async def test_diagram_source_returned_verbatim_never_500(
    client: AsyncClient, logged_in_headers: dict, stub_diagram_render
):
    """D2 is opaque text returned as the `d2` field untouched — the read never 500s.

    Whatever real source was stored (even content that would not compile) comes
    straight back verbatim on `d2`; a blank or whitespace-only store is "no
    diagram" and normalises to the empty payload (`d2: null, svg: null`). The SVG
    render is stubbed here (its real behaviour is tested separately), so this
    focuses on the `d2` verbatim + never-500 contract.
    """
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    for raw, expected_d2 in (
        ("not valid d2 {{{", "not valid d2 {{{"),
        ("shape: sequence_diagram\na -> b: hi", "shape: sequence_diagram\na -> b: hi"),
        ("  shape: sequence_diagram  ", "  shape: sequence_diagram  "),  # real content kept verbatim, not trimmed
        ("", None),
        ("   ", None),  # whitespace-only → no diagram
        (" \n\t ", None),
    ):
        await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=raw)
        response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK, raw
        body = response.json()
        assert body["d2"] == expected_d2, raw
        # No diagram → no SVG; real source → the (stubbed) server render.
        assert body["svg"] == (None if expected_d2 is None else stub_diagram_render), raw


@pytest.mark.skipif(shutil.which("d2") is None, reason="the `d2` binary is not installed")
async def test_diagram_server_renders_svg_real(client: AsyncClient, logged_in_headers: dict):
    """With the real `d2` compiler present, GET /diagram returns a server-rendered SVG (D.6).

    Valid stored D2 → `svg` is real SVG markup the frontend displays directly;
    non-compilable stored D2 → `svg` is null (logged, never 500). Not stubbed —
    this is the end-to-end backend-render contract.
    """
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")

    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=_SEED_D2)
    body = (await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)).json()
    assert body["d2"] == _SEED_D2
    assert body["svg"] is not None
    assert "<svg" in body["svg"]

    # Non-compilable source still 200s; the render fails closed to svg: null.
    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2="not valid d2 {{{")
    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": "not valid d2 {{{", "svg": None}


async def test_diagram_render_failure_degrades_to_null_svg(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """A render failure returns the `d2` with `svg: null` and a 200 — never a 500 (hermetic).

    Mirrors the gated real test's failure branch without needing the `d2` binary,
    so CI exercises the fail-closed path regardless of the environment.
    """
    from langflow.lothal.d2_compile import D2RenderResult

    async def _failing_render(_src):
        return D2RenderResult(error="1:1: connection missing destination")

    monkeypatch.setattr(lothal_api, "render_d2", _failing_render)

    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=_SEED_D2)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": _SEED_D2, "svg": None}


async def test_diagram_compiler_unavailable_degrades_to_null_svg(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """If the `d2` compiler is unavailable, the read still 200s with the `d2` and `svg: null`.

    A missing compiler is an environment fault, not a broken diagram — the source
    is still returned so nothing is lost; the canvas just shows no SVG.
    """

    async def _unavailable_render(_src):
        raise D2CompilerUnavailableError

    monkeypatch.setattr(lothal_api, "render_d2", _unavailable_render)

    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    await _set_phase_and_d2(UUID(project_id), phase="ARCHITECTURE", diagram_d2=_SEED_D2)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": _SEED_D2, "svg": None}


async def test_diagram_legacy_xyflow_only_reads_empty(client: AsyncClient, logged_in_headers: dict):
    """A pre-Epic-D project with only `diagram_json` (no D2) reads as empty until migrated (D.13)."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "ARCHITECTURE"
        project.diagram_json = json.dumps({"nodes": [{"id": "x"}], "edges": []})
        project.diagram_d2 = None

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": None, "svg": None}


async def test_diagram_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """Ownership is resolved before the phase gate — another user's project 404s, never 403."""
    async with session_scope() as session:
        # Phase set past CLARIFICATION so a 403 can't mask the 404 we're asserting.
        foreign = Project(name="Theirs", user_id=user_two.id, phase="ARCHITECTURE")
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        for project_id in (PROJECT_ID, str(foreign_pk)):
            response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND, project_id
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


# --- Artifacts read (Epic E.4) ------------------------------------------------


_DIAGRAM_PATHS = (
    "diagrams/context.d2",
    "diagrams/container.d2",
    "diagrams/data-model.d2",
    "diagrams/sequence.d2",
)


async def _set_phase_and_artifacts(project_pk: UUID, *, phase: str, artifacts: dict[str, str] | None) -> None:
    """Seed a project's phase and raw `artifacts` map directly (mirrors `_set_phase_and_d2`)."""
    async with session_scope() as session:
        project = await session.get(Project, project_pk)
        project.phase = phase
        project.artifacts = artifacts


async def test_artifacts_403_in_clarification(client: AsyncClient, logged_in_headers: dict):
    """A fresh project sits in CLARIFICATION, before any artifact exists → 403 (mirrors /diagram)."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_artifacts_empty_before_generation_completes(client: AsyncClient, logged_in_headers: dict):
    """Past CLARIFICATION but before the generator emits → empty map, not 500."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    await _set_phase_and_artifacts(UUID(project_id), phase="ARCHITECTURE", artifacts=None)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"artifacts": {}, "svgs": {}}


async def test_artifacts_returns_map_and_svg_per_diagram(
    client: AsyncClient, logged_in_headers: dict, stub_diagram_render
):
    """A seeded artifact map comes back verbatim, with an SVG rendered per `diagrams/*.d2` entry.

    The ADR (`adr.md`) is Markdown and gets no SVG; every diagram entry is keyed
    into `svgs` by its artifact path with the (stubbed) server render.
    """
    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    seeded = _seed_artifacts(_SEED_D2)
    await _set_phase_and_artifacts(UUID(project_id), phase="ARCHITECTURE", artifacts=seeded)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    assert set(body) == {"artifacts", "svgs"}
    # The full file-map is returned verbatim — ADR plus the four diagrams.
    assert body["artifacts"] == seeded
    # One SVG per diagram, keyed by path; the ADR is not rendered.
    assert set(body["svgs"]) == set(_DIAGRAM_PATHS)
    assert "adr.md" not in body["svgs"]
    assert all(svg == stub_diagram_render for svg in body["svgs"].values())


async def test_artifacts_readable_in_later_phases(client: AsyncClient, logged_in_headers: dict, stub_diagram_render):
    """The artifact map stays readable through the prototype stage, code generation, and done."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    seeded = _seed_artifacts(_SEED_D2)
    for phase in ("ARCHITECTURE", "PROTOTYPE", "CODE_GENERATION", "DONE"):
        await _set_phase_and_artifacts(UUID(project_id), phase=phase, artifacts=seeded)
        response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK, phase
        body = response.json()
        assert body["artifacts"] == seeded, phase
        assert body["svgs"] == dict.fromkeys(_DIAGRAM_PATHS, stub_diagram_render), phase


async def test_artifacts_render_failure_degrades_to_null_svg(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """A render failure returns the map with `svg: null` per diagram and a 200 — never a 500.

    The artifact content is still returned in full; only the SVGs fail closed. The
    `adr.md` entry stays out of `svgs` regardless.
    """
    from langflow.lothal.d2_compile import D2RenderResult

    async def _failing_render(_src):
        return D2RenderResult(error="1:1: connection missing destination")

    monkeypatch.setattr(lothal_api, "render_d2", _failing_render)

    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    seeded = _seed_artifacts(_SEED_D2)
    await _set_phase_and_artifacts(UUID(project_id), phase="ARCHITECTURE", artifacts=seeded)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["artifacts"] == seeded
    assert body["svgs"] == dict.fromkeys(_DIAGRAM_PATHS, None)


async def test_artifacts_compiler_unavailable_degrades_to_null_svg(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """If the `d2` compiler is unavailable, the read still 200s with the map and `svg: null` per diagram."""

    async def _unavailable_render(_src):
        raise D2CompilerUnavailableError

    monkeypatch.setattr(lothal_api, "render_d2", _unavailable_render)

    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    seeded = _seed_artifacts(_SEED_D2)
    await _set_phase_and_artifacts(UUID(project_id), phase="ARCHITECTURE", artifacts=seeded)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["artifacts"] == seeded
    assert body["svgs"] == dict.fromkeys(_DIAGRAM_PATHS, None)


@pytest.mark.skipif(shutil.which("d2") is None, reason="the `d2` binary is not installed")
async def test_artifacts_server_renders_svg_real(client: AsyncClient, logged_in_headers: dict):
    """With the real `d2` compiler present, GET /artifacts renders real SVG per diagram (E.4).

    Every seeded `diagrams/*.d2` entry compiles, so each `svgs` value is real SVG
    markup; the ADR stays out of `svgs`. Not stubbed — the end-to-end backend
    render across the full set.
    """
    project_id = await _create_chat_project(client, logged_in_headers, name="Artifacts")
    seeded = _seed_artifacts(_SEED_D2)
    await _set_phase_and_artifacts(UUID(project_id), phase="ARCHITECTURE", artifacts=seeded)

    body = (await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)).json()
    assert body["artifacts"] == seeded
    assert set(body["svgs"]) == set(_DIAGRAM_PATHS)
    assert all("<svg" in svg for svg in body["svgs"].values())


async def test_artifacts_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """Ownership is resolved before the phase gate — another user's project 404s, never 403."""
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id, phase="ARCHITECTURE")
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        for project_id in (PROJECT_ID, str(foreign_pk)):
            response = await client.get(f"api/v1/lothal/projects/{project_id}/artifacts", headers=logged_in_headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND, project_id
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


async def test_chat_rejects_blank_content(client: AsyncClient, logged_in_headers: dict):
    project_id = await _create_chat_project(client, logged_in_headers)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "   "}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_chat_llm_failure_rolls_back_the_turn(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """An LLM failure maps to 502 and leaves no half-written turn behind."""
    project_id = await _create_chat_project(client, logged_in_headers)

    async def boom(_messages, **_kwargs):
        msg = "Claude returned an empty response."
        raise LLMConnectionError(msg)

    monkeypatch.setattr(clarification_engine, "call_llm", boom)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "hi"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY

    # The user message was rolled back with the failed turn — history is empty.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert messages == []


async def test_chat_and_messages_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """Both live chat routes resolve ownership first: another user's project 404s."""
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id)
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        assert (
            await client.post(
                f"api/v1/lothal/projects/{foreign_pk}/chat", json={"content": "hi"}, headers=logged_in_headers
            )
        ).status_code == status.HTTP_404_NOT_FOUND
        assert (
            await client.get(f"api/v1/lothal/projects/{foreign_pk}/messages", headers=logged_in_headers)
        ).status_code == status.HTTP_404_NOT_FOUND
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


@pytest.mark.api_key_required
async def test_debug_llm_real_subscription(client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch):
    """Story 0.4 acceptance: a real model reply comes back through the endpoint.

    Excluded from the default suite (`api_key_required`); run with a live
    Claude Code subscription via `-m api_key_required`. Pinned to Haiku — all
    real-LLM tests use `claude-haiku-4-5`.
    """
    if find_spec("claude_agent_sdk") is None:
        pytest.skip("claude-agent-sdk not installed")
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-haiku-4-5")

    response = await client.post(
        "api/v1/lothal/debug/llm", json={"message": "say hi"}, headers=logged_in_headers_super_user
    )

    assert response.status_code == status.HTTP_200_OK
    reply = response.json()["response"]
    assert isinstance(reply, str)
    assert reply.strip()


# A realistic opening description plus answers to the questions a clarification
# turn is likely to ask. Detailed answers let the model converge to clarity
# within a handful of turns; the trailing nudges close out any lingering question
# so the test stays bounded if the model keeps probing.
_SMOKE_DESCRIPTION = (
    "I want to build a recipe-sharing web app where home cooks can post their own "
    "recipes, browse and search recipes by ingredient or cuisine, save favourites, "
    "and leave ratings and comments on each other's recipes."
)
_SMOKE_ANSWERS = [
    "It's for home cooks and food enthusiasts — anyone who wants to share or "
    "discover recipes; no professional chefs needed.",
    "Core features: post a recipe with ingredients, steps and a photo; search "
    "and filter by ingredient and cuisine; save favourites; rate and comment.",
    "Each recipe has a title, ingredient list, step-by-step instructions, a "
    "photo, prep/cook time, and tags. Users have a profile with their recipes.",
    "Main flows: sign up, post a recipe, search/browse, open a recipe, save it, and leave a rating or comment.",
    "That covers everything I need — please write the product spec now.",
    "Yes, that's complete. Please summarise the specification.",
]
# Hard cap on turns so a model that never stops asking fails loudly instead of
# looping forever against a live subscription.
_SMOKE_MAX_TURNS = 8


@pytest.mark.api_key_required
async def test_clarification_end_to_end_real_subscription(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Story 1.4 acceptance: a real clarification conversation reaches clarity end-to-end.

    Excluded from the default suite (`api_key_required`); run with a live Claude
    Code subscription via `-m api_key_required`. Pinned to Haiku — all real-LLM
    tests use `claude-haiku-4-5`.

    Drives the live `POST /chat` endpoint with a realistic app description and
    progressively detailed answers. Asserts the model asks focused questions with
    tappable suggestions while gathering requirements, then within a few turns
    emits `[CLARITY_REACHED]`: the PRD is drafted and stored (token stripped,
    surfaced by `GET /prd`) while the project HOLDS in CLARIFICATION (phase-gates —
    no auto-advance), and the explicit `POST /prd/approve` is what moves it to
    ARCHITECTURE.
    """
    if find_spec("claude_agent_sdk") is None:
        pytest.skip("claude-agent-sdk not installed")
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-haiku-4-5")

    project_id = await _create_chat_project(client, logged_in_headers, name="Recipe App")

    async def send(content: str) -> dict:
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/chat", json={"content": content}, headers=logged_in_headers
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()

    # Opening turn: a vague idea should keep the project in CLARIFICATION and draw
    # a focused, non-empty question back.
    reply = await send(_SMOKE_DESCRIPTION)
    assert reply["role"] == "ASSISTANT"
    assert reply["phase"] == "CLARIFICATION"
    assert reply["content"].strip()
    assert "[CLARITY_REACHED]" not in reply["content"]

    saw_suggestions = bool(reply["suggestions"])

    async def drafted_prd() -> str | None:
        # phase-gates: clarity no longer advances the phase — it drafts the PRD and
        # HOLDS in CLARIFICATION. The clarity signal is `prd_content` being set (a
        # turn's reply is stamped with the phase it ran under, always CLARIFICATION).
        project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
        return project["prd_content"]

    # Keep answering until the model reaches clarity (a PRD is drafted), falling
    # back to a generic nudge once the canned answers run out.
    answers = iter(_SMOKE_ANSWERS)
    turns = 1
    while not await drafted_prd() and turns < _SMOKE_MAX_TURNS:
        answer = next(answers, "That's everything you need — please write the spec now.")
        reply = await send(answer)
        turns += 1
        saw_suggestions = saw_suggestions or bool(reply["suggestions"])

    # Clarity must be reached within the bounded number of turns, and the project
    # HOLDS in CLARIFICATION with a drafted PRD (no auto-advance).
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["prd_content"], f"never reached clarity in {turns} turns"
    assert project["phase"] == "CLARIFICATION", f"phase should hold at clarification, got {project['phase']}"

    # At least one clarification turn offered tappable suggestions (focused questions).
    assert saw_suggestions, "no clarification turn returned suggestions"

    # The clarity turn's reply is a short handoff (not the PRD) with the token stripped.
    assert "[CLARITY_REACHED]" not in reply["content"]
    assert reply["suggestions"] == []

    # The PRD is stored on the main page and surfaced by `GET /prd`, token-free.
    prd = (await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)).json()
    assert prd["content"], "PRD was not stored"
    assert "[CLARITY_REACHED]" not in prd["content"]
    assert project["prd_content"] == prd["content"]

    # History replays the whole exchange, oldest first, alternating user/assistant.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert len(messages) == turns * 2  # each turn = user + assistant
    assert messages[0]["role"] == "USER"
    assert all("[CLARITY_REACHED]" not in m["content"] for m in messages)

    # The explicit approve is the gate that advances CLARIFICATION → ARCHITECTURE.
    approve = await client.post(f"api/v1/lothal/projects/{project_id}/prd/approve", headers=logged_in_headers)
    assert approve.status_code == status.HTTP_200_OK
    assert approve.json() == {"phase": "ARCHITECTURE"}


# --- Prototype stage (Epic UI, Stories U.4-U.7) ------------------------------
# The prototype stage drives Open Design (OD) as a headless prototyping engine.
# Lothal is OD's HTTP client; these tests mock OD's daemon with respx (the same
# way the gateway tests mock their upstream) so the engine + endpoints are
# verified end-to-end against a stubbed OD, never a live one.

OD_BASE = "http://open-design:7456"

# A representative OD project file carrying an artifact manifest, plus a plain
# file with none (which must be filtered out — only artifacts surface).
OD_ARTIFACT_FILE = {
    "name": "home.html",
    "path": "home.html",
    "kind": "file",
    "artifactKind": "prototype",
    "artifactManifest": {"kind": "prototype", "title": "Home screen"},
}
OD_ARTIFACT_FILE_2 = {
    "name": "about.html",
    "path": "about.html",
    "kind": "file",
    "artifactKind": "prototype",
    "artifactManifest": {"kind": "prototype", "title": "About screen"},
}
OD_PLAIN_FILE = {"name": "notes.txt", "path": "notes.txt", "kind": "file"}


def _mock_od_discovery(*, projects=None, runs=None):
    """Register the GET probes `generate` runs before create (OD-level idempotency).

    seed_and_generate first lists OD projects (to reuse a previously-tagged one) and
    the chosen project's runs (to avoid double-running). The happy path returns none
    of each, so generate proceeds to create + start_run.
    """
    respx.get(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json=projects or []))
    respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=runs or []))


@pytest.fixture
def _od_env(monkeypatch):
    """Pin the OD client env to a known host with no token and no agent PATCH.

    Blanking `LOTHAL_OD_AGENT_ID` skips the best-effort `PATCH /api/app-config`
    (its own dedicated test re-enables it), so the common-path tests only need to
    mock create/run/files/runs.
    """
    monkeypatch.setenv("LOTHAL_OD_BASE_URL", OD_BASE)
    monkeypatch.delenv("LOTHAL_OD_API_TOKEN", raising=False)
    monkeypatch.delenv("OD_API_TOKEN", raising=False)
    monkeypatch.delenv("LOTHAL_OD_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "")
    monkeypatch.setenv("LOTHAL_OD_SKILL_ID", "")
    # Default the prototype tests to "no BYOK": the endpoints resolve the user's
    # subscription token (falling back to the server CLAUDE_CODE_OAUTH_TOKEN) and
    # inject it into OD's agent, so clear the env token to keep the no-key path
    # deterministic. The BYOK-injection case has its own test that sets it.
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)


async def _make_prototype_project(
    client: AsyncClient,
    headers: dict,
    *,
    phase: str = "PROTOTYPE",
    od_project_id: str | None = None,
    od_conversation_id: str | None = None,
    prototype_status: str = "IDLE",
    prd: str | None = "A todo app for individuals.",
    diagram_d2: str | None = "user -> api: submit",
) -> str:
    """Create a project and force it into the given prototype-stage state."""
    project_id = await _create_chat_project(client, headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = phase
        project.prd_content = prd
        project.diagram_d2 = diagram_d2
        project.od_project_id = od_project_id
        project.od_conversation_id = od_conversation_id
        project.prototype_status = prototype_status
        session.add(project)
    return project_id


@pytest.mark.parametrize("phase", ["CLARIFICATION", "ARCHITECTURE"])
async def test_get_prototype_403_before_prototype_phase(client: AsyncClient, logged_in_headers: dict, phase: str):
    """`GET /prototype` is phase-gated: a read before the prototype stage is a 403."""
    project_id = await _make_prototype_project(client, logged_in_headers, phase=phase)
    response = await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_prototype_idle_before_generation(client: AsyncClient, logged_in_headers: dict):
    """In PROTOTYPE but not yet seeded, `GET /prototype` reports IDLE with no OD call."""
    project_id = await _make_prototype_project(client, logged_in_headers)
    # No respx mock: an unlinked project never calls OD (collect_state short-circuits).
    response = await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "IDLE"
    assert body["od_project_id"] is None
    assert body["artifacts"] == []


@pytest.mark.usefixtures("_od_env")
async def test_generate_seeds_od_and_reports_generating(client: AsyncClient, logged_in_headers: dict):
    """U.4 acceptance: entering PROTOTYPE generation creates one OD project + run, persists the linkage."""
    project_id = await _make_prototype_project(client, logged_in_headers)

    with respx.mock:
        _mock_od_discovery()
        create = respx.post(f"{OD_BASE}/api/projects").mock(
            return_value=httpx.Response(200, json={"id": "od-proj-1", "name": "Chat"})
        )
        run = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-1", "conversationId": "conv-1"})
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "GENERATING"
    assert body["od_project_id"] == "od-proj-1"
    assert body["od_conversation_id"] == "conv-1"
    assert create.call_count == 1
    assert run.call_count == 1

    # The run carries the brief built from the PRD + diagram (the single-chat
    # bridge: OD is seeded from context the user already produced, U.10).
    run_body = json.loads(run.calls.last.request.content)
    assert run_body["projectId"] == "od-proj-1"
    assert "todo app" in run_body["message"]

    # The linkage is persisted, and one ASSISTANT stage-entry marker lands in the
    # single chat thread (U.10).
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "PROTOTYPE"
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert len(messages) == 1
    assert messages[0]["role"] == "ASSISTANT"
    assert messages[0]["phase"] == "PROTOTYPE"


@pytest.mark.usefixtures("_od_env")
async def test_generate_is_idempotent_on_reentry(client: AsyncClient, logged_in_headers: dict):
    """U.4 acceptance: re-entering generation reuses the OD project — no duplicate project/run."""
    project_id = await _make_prototype_project(client, logged_in_headers)

    with respx.mock:
        _mock_od_discovery()
        create = respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-proj-1"}))
        respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-1", "conversationId": "conv-1"})
        )
        first = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers)
        second = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers)

    assert first.status_code == second.status_code == status.HTTP_200_OK
    # The second call reused the existing OD project: create was called exactly once.
    assert create.call_count == 1
    assert second.json()["od_project_id"] == "od-proj-1"
    # Only one stage-entry marker, despite two generate calls.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert len([m for m in messages if m["role"] == "ASSISTANT"]) == 1


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PLAN", "CODE_GENERATION", "DONE"])
async def test_generate_rejected_outside_prototype(client: AsyncClient, logged_in_headers: dict, phase: str):
    """Generation is only valid in PROTOTYPE; any other phase is a 409 and never calls OD."""
    project_id = await _make_prototype_project(client, logged_in_headers, phase=phase)
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.usefixtures("_od_env")
async def test_generate_points_od_agent_at_gateway(client: AsyncClient, logged_in_headers, monkeypatch):
    """U.4: generation points OD's codex agent at Lothal's gateway via PATCH /api/app-config."""
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "codex")
    monkeypatch.setenv("LOTHAL_GATEWAY_PUBLIC_URL", "http://backend:7860/api/v1/lothal/gateway/v1")
    monkeypatch.setenv("LOTHAL_GATEWAY_TOKEN", "gw-token")
    project_id = await _make_prototype_project(client, logged_in_headers)

    with respx.mock:
        _mock_od_discovery()
        cfg = respx.put(f"{OD_BASE}/api/app-config").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-proj-1"}))
        respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={"runId": "run-1"}))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert cfg.call_count == 1
    patched = json.loads(cfg.calls.last.request.content)
    assert patched["agentCliEnv"]["codex"]["OPENAI_BASE_URL"] == "http://backend:7860/api/v1/lothal/gateway/v1"
    assert patched["agentCliEnv"]["codex"]["OPENAI_API_KEY"] == "gw-token"
    # Same write pre-completes OD's onboarding and pins the agent, so the embedded
    # project page renders directly instead of bouncing to the sign-in chooser.
    assert patched["onboardingCompleted"] is True
    assert patched["agentId"] == "codex"


@pytest.mark.usefixtures("_od_env")
async def test_generate_injects_byok_token_for_claude_agent(client: AsyncClient, logged_in_headers, monkeypatch):
    """Generation hands the claude agent the user's token as CLAUDE_CODE_OAUTH_TOKEN.

    It runs the subscription natively via agentCliEnv — no gateway/OPENAI_* — so the
    prototype stage runs on the same key the code stage does.
    """
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "claude")
    # No per-user variable in the test DB, so _resolve_user_byok falls back to the
    # server subscription token — enough to prove the injection wiring.
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-user-key")
    project_id = await _make_prototype_project(client, logged_in_headers)

    with respx.mock:
        _mock_od_discovery()
        cfg = respx.put(f"{OD_BASE}/api/app-config").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-proj-1"}))
        respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={"runId": "run-1"}))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert cfg.call_count == 1
    patched = json.loads(cfg.calls.last.request.content)
    # The user's key reaches the claude CLI natively; no OpenAI/gateway plumbing.
    assert patched["agentCliEnv"]["claude"]["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat-user-key"  # noqa: S105
    assert "OPENAI_BASE_URL" not in patched["agentCliEnv"]["claude"]
    assert "OPENAI_API_KEY" not in patched["agentCliEnv"]["claude"]
    assert patched["agentId"] == "claude"
    assert patched["onboardingCompleted"] is True
    # The response body never carries the token back to the browser.
    assert "sk-ant-oat-user-key" not in response.text


@pytest.mark.usefixtures("_od_env")
async def test_generate_succeeds_even_if_agent_config_fails(client: AsyncClient, logged_in_headers, monkeypatch):
    """Pointing OD at the gateway is best-effort: a failed PATCH must not sink generation."""
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "codex")
    project_id = await _make_prototype_project(client, logged_in_headers)

    with respx.mock:
        _mock_od_discovery()
        respx.put(f"{OD_BASE}/api/app-config").mock(side_effect=httpx.ConnectError("nope"))
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-proj-1"}))
        respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={"runId": "run-1"}))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "GENERATING"


@pytest.mark.usefixtures("_od_env")
async def test_generate_maps_od_failure_to_502(client: AsyncClient, logged_in_headers: dict):
    """A reachable-but-unhappy OD (or unreachable daemon) surfaces as a 502, never a 500."""
    project_id = await _make_prototype_project(client, logged_in_headers)
    with respx.mock:
        # The OD-reuse probe finds none, then the create call fails → 502.
        respx.get(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json=[]))
        respx.post(f"{OD_BASE}/api/projects").mock(side_effect=httpx.ConnectError("boom"))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers
        )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY


async def test_generate_503_when_od_base_url_blank(client: AsyncClient, logged_in_headers, monkeypatch):
    """An explicitly blank OD base URL is a configuration error (503), not a 502."""
    monkeypatch.setenv("LOTHAL_OD_BASE_URL", "")
    monkeypatch.setenv("LOTHAL_OD_AGENT_ID", "")
    project_id = await _make_prototype_project(client, logged_in_headers)
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers)
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.usefixtures("_od_env")
async def test_get_prototype_reports_ready_and_lists_artifacts(client: AsyncClient, logged_in_headers: dict):
    """U.5 acceptance: a seeded project with a succeeded run reports READY + the artifact set."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", od_conversation_id="conv-1", prototype_status="GENERATING"
    )

    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(
            return_value=httpx.Response(200, json=[OD_ARTIFACT_FILE, OD_PLAIN_FILE])
        )
        respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "run-1", "status": "succeeded", "createdAt": "2026-01-01"}])
        )
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home design</html>")
        )
        response = await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "READY"
    # Only the manifest-bearing file surfaces; the plain file is filtered out.
    assert [a["path"] for a in body["artifacts"]] == ["home.html"]
    assert body["artifacts"][0]["title"] == "Home screen"
    # The primary HTML design is rendered inline.
    assert body["preview_html"] == "<html>home design</html>"

    # The forward READY transition is persisted (next read is fast / badge reflects it).
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.prototype_status == PrototypeStatus.READY.value


@pytest.mark.usefixtures("_od_env")
async def test_get_prototype_degrades_when_od_unreachable(client: AsyncClient, logged_in_headers: dict):
    """A read must not 502 the polling UI: an unreachable OD degrades to the stored status, no artifacts."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="GENERATING"
    )
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(side_effect=httpx.ConnectError("down"))
        respx.get(f"{OD_BASE}/api/runs").mock(side_effect=httpx.ConnectError("down"))
        response = await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "GENERATING"
    assert body["artifacts"] == []


@pytest.mark.usefixtures("_od_env")
async def test_get_prototype_embed_url_uses_public_base(client: AsyncClient, logged_in_headers, monkeypatch):
    """`embed_url` is resolved from the public OD base when configured (the iframe surface, U.9)."""
    monkeypatch.setenv("LOTHAL_OD_PUBLIC_BASE_URL", "https://od.lothal.app")
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="GENERATING"
    )
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        response = await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)
    assert response.json()["embed_url"] == "https://od.lothal.app/projects/od-proj-1"


@pytest.mark.usefixtures("_od_env")
async def test_refine_starts_run_in_conversation(client: AsyncClient, logged_in_headers: dict):
    """U.6 acceptance: refine starts a new OD run on the stored conversation and returns to GENERATING."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", od_conversation_id="conv-1", prototype_status="READY"
    )
    with respx.mock:
        run = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-2", "conversationId": "conv-1"})
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/refine",
            json={"content": "make the header darker"},
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "GENERATING"
    run_body = json.loads(run.calls.last.request.content)
    assert run_body["projectId"] == "od-proj-1"
    assert run_body["conversationId"] == "conv-1"
    assert run_body["message"] == "make the header darker"


async def test_refine_rejected_before_generation(client: AsyncClient, logged_in_headers: dict):
    """Refining a project with no OD prototype yet is a 409 (nothing to refine)."""
    project_id = await _make_prototype_project(client, logged_in_headers)  # od_project_id is None
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/prototype/refine",
        json={"content": "tweak it"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_refine_rejected_outside_prototype(client: AsyncClient, logged_in_headers: dict):
    """Refine is only valid in PROTOTYPE."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, phase="CODE_GENERATION", od_project_id="od-proj-1"
    )
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/prototype/refine",
        json={"content": "tweak it"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_refine_rejects_blank_instruction(client: AsyncClient, logged_in_headers: dict):
    """A blank refine instruction is a 422 before any OD call."""
    project_id = await _make_prototype_project(client, logged_in_headers, od_project_id="od-proj-1")
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/prototype/refine",
        json={"content": "   "},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.usefixtures("_od_env")
async def test_approve_copies_artifacts_and_advances(client: AsyncClient, logged_in_headers: dict):
    """U.7/U-PLAN acceptance: approve copies artifacts, stamps approval, posts a summary, advances to PLAN."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", od_conversation_id="conv-1", prototype_status="READY"
    )

    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(
            return_value=httpx.Response(200, json=[OD_ARTIFACT_FILE, OD_PLAIN_FILE])
        )
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home</html>")
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/approve", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"phase": "PLAN"}

    # The finalised artifact is copied into Lothal's own store (DB-as-source-of-truth),
    # status is APPROVED with an approval timestamp, and the phase advanced to PLAN.
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.phase == "PLAN"
        assert project.prototype_status == PrototypeStatus.APPROVED.value
        assert project.prototype_approved_at is not None
        rows = (await session.exec(select(PrototypeArtifact).where(PrototypeArtifact.project_id == project.id))).all()
        assert [r.od_path for r in rows] == ["home.html"]
        assert rows[0].content == "<html>home</html>"
        assert rows[0].title == "Home screen"

    # A summary lands in the single chat thread (U.10).
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert any(m["role"] == "ASSISTANT" and "approved" in m["content"].lower() for m in messages)

    # The approved prototype stays readable post-advance, served from the DB copy.
    state = (await client.get(f"api/v1/lothal/projects/{project_id}/prototype", headers=logged_in_headers)).json()
    assert state["status"] == "APPROVED"
    assert [a["path"] for a in state["artifacts"]] == ["home.html"]


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PLAN", "CODE_GENERATION", "DONE"])
async def test_approve_prototype_rejected_outside_prototype(client: AsyncClient, logged_in_headers: dict, phase: str):
    """Approve is only valid in PROTOTYPE; any other phase is a 409 and a no-op."""
    project_id = await _make_prototype_project(client, logged_in_headers, phase=phase, od_project_id="od-proj-1")
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == phase


@pytest.mark.usefixtures("_od_env")
async def test_approve_with_no_artifacts_still_advances(client: AsyncClient, logged_in_headers: dict):
    """Approve with an empty OD result: no rows persisted, the no-artifacts summary posted, phase still advances."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="READY"
    )
    with respx.mock:
        # Only a non-artifact file → collect_for_approval yields nothing.
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(
            return_value=httpx.Response(200, json=[OD_PLAIN_FILE])
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/approve", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"phase": "PLAN"}
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.phase == "PLAN"
        assert project.prototype_status == PrototypeStatus.APPROVED.value
        assert project.prototype_approved_at is not None
        rows = (await session.exec(select(PrototypeArtifact).where(PrototypeArtifact.project_id == project.id))).all()
        assert rows == []  # nothing to copy

    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    summaries = [m["content"] for m in messages if m["role"] == "ASSISTANT"]
    assert any("approved" in s.lower() and "artifact" not in s.lower() for s in summaries)


async def test_approve_rejected_before_prototype_ready(client: AsyncClient, logged_in_headers: dict):
    """Approve is a 409 until generation has produced a READY prototype — no premature advance."""
    # Never generated (no OD link, status IDLE): approving must not advance the phase.
    not_generated = await _make_prototype_project(client, logged_in_headers)
    r1 = await client.post(f"api/v1/lothal/projects/{not_generated}/prototype/approve", headers=logged_in_headers)
    assert r1.status_code == status.HTTP_409_CONFLICT

    # Linked but still GENERATING: also rejected (no OD call needed — respx unmocked
    # would error if it tried, so a clean 409 proves it short-circuits).
    generating = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="GENERATING"
    )
    r2 = await client.post(f"api/v1/lothal/projects/{generating}/prototype/approve", headers=logged_in_headers)
    assert r2.status_code == status.HTTP_409_CONFLICT

    async with session_scope() as session:
        assert (await session.get(Project, UUID(generating))).phase == "PROTOTYPE"


@pytest.mark.usefixtures("_od_env")
async def test_approve_summary_pluralises_artifact_count(client: AsyncClient, logged_in_headers: dict):
    """Two artifacts → both persisted and the summary reads 'with 2 artifacts:'."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="READY"
    )
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(
            return_value=httpx.Response(200, json=[OD_ARTIFACT_FILE, OD_ARTIFACT_FILE_2])
        )
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>home</html>")
        )
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/raw/about.html").mock(
            return_value=httpx.Response(200, text="<html>about</html>")
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/approve", headers=logged_in_headers
        )

    assert response.status_code == status.HTTP_200_OK
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        rows = (await session.exec(select(PrototypeArtifact).where(PrototypeArtifact.project_id == project.id))).all()
        assert {r.od_path for r in rows} == {"home.html", "about.html"}
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert any("with 2 artifacts" in m["content"] for m in messages if m["role"] == "ASSISTANT")


@pytest.mark.usefixtures("_od_env")
async def test_refine_maps_od_failure_to_502(client: AsyncClient, logged_in_headers: dict):
    """A failed OD run on refine surfaces as 502 (not a leaked 500)."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", od_conversation_id="conv-1", prototype_status="READY"
    )
    with respx.mock:
        respx.post(f"{OD_BASE}/api/runs").mock(side_effect=httpx.ConnectError("down"))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/refine",
            json={"content": "tweak"},
            headers=logged_in_headers,
        )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.usefixtures("_od_env")
async def test_approve_maps_od_failure_to_502_and_does_not_advance(client: AsyncClient, logged_in_headers: dict):
    """A failed OD pull on approve is a 502 and leaves the project in PROTOTYPE (fail-loud, unlike GET's degrade)."""
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", prototype_status="READY"
    )
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-proj-1/files").mock(side_effect=httpx.ConnectError("down"))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/prototype/approve", headers=logged_in_headers
        )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.phase == "PROTOTYPE"  # not advanced
        assert project.prototype_status == PrototypeStatus.READY.value
        rows = (await session.exec(select(PrototypeArtifact).where(PrototypeArtifact.project_id == project.id))).all()
        assert rows == []


async def test_generate_idempotent_does_not_clobber_ready_status(client: AsyncClient, logged_in_headers: dict):
    """Re-generating an already-linked, READY project returns READY and makes no OD call.

    No respx mock is registered: if the handler erroneously hit OD it would fail on a
    real connection, so a green result also proves the idempotent path is OD-free.
    """
    project_id = await _make_prototype_project(
        client, logged_in_headers, od_project_id="od-proj-1", od_conversation_id="conv-1", prototype_status="READY"
    )
    response = await client.post(f"api/v1/lothal/projects/{project_id}/prototype/generate", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "READY"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.prototype_status == PrototypeStatus.READY.value


async def test_prototype_routes_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """Ownership is checked first on every prototype route: another user's project 404s, never 403/409."""
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id, phase="PROTOTYPE", od_project_id="od-x")
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        calls = [
            ("GET", f"api/v1/lothal/projects/{foreign_pk}/prototype", None),
            ("POST", f"api/v1/lothal/projects/{foreign_pk}/prototype/generate", None),
            ("POST", f"api/v1/lothal/projects/{foreign_pk}/prototype/refine", {"content": "x"}),
            ("POST", f"api/v1/lothal/projects/{foreign_pk}/prototype/approve", None),
        ]
        for method, path, body in calls:
            response = await client.request(method, path, json=body, headers=logged_in_headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND, (method, path)
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


# --- Plan stage (Epic U-PLAN) ------------------------------------------------
# The plan stage bridges to the standalone Lothal PM service (the verification-
# driven PM tree). These tests mock the PM daemon with respx (the same way the
# prototype tests mock OD), so the bridge + endpoints are verified end-to-end
# against a stubbed PM, never a live one. The browser-facing API IS the canonical
# Lothal API; the PM service is never called by the browser, only by the bridge.

PM_BASE = "http://pm:8000"
# Fixed PM-issued ids for the tests (the pm_project_id column is a UUID, so these
# must be real UUIDs, not placeholder strings).
PM_ID_CREATED = "11111111-1111-1111-1111-111111111111"
PM_ID_EXISTING = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
async def _reset_pm_singleton():
    """Reset the process-wide PM client around every test.

    ``pm_client()`` caches one client for the process (pool + JWT reuse in prod),
    so without this a client built under one test's env + respx mock would leak
    into the next — notably breaking the blank-base-URL 503 case, which needs
    ``from_env()`` to re-run.
    """
    from langflow.lothal.pm_client import aclose_pm_client

    await aclose_pm_client()
    yield
    await aclose_pm_client()


@pytest.fixture
def _pm_env(monkeypatch):
    """Pin the PM client to a known host with the default service credentials."""
    monkeypatch.setenv("LOTHAL_PM_BASE_URL", PM_BASE)
    monkeypatch.setenv("LOTHAL_PM_USER", "admin")
    monkeypatch.setenv("LOTHAL_PM_PASSWORD", "admin")


def _mock_pm_login():
    """Register `POST /api/auth/login` → a bearer token (every PM call authenticates first)."""
    respx.post(f"{PM_BASE}/api/auth/login").mock(
        return_value=httpx.Response(200, json={"access_token": "pm-test-token", "token_type": "bearer"})
    )


async def _make_plan_project(client: AsyncClient, headers: dict, *, phase: str = "PLAN") -> str:
    """Create a project and force it into the given phase for the plan-stage tests."""
    project_id = await _create_chat_project(client, headers)
    await _set_phase_and_d2(UUID(project_id), phase=phase, diagram_d2=None)
    return project_id


@pytest.mark.parametrize("phase", ["CLARIFICATION", "ARCHITECTURE", "PROTOTYPE"])
async def test_get_plan_403_before_plan_phase(client: AsyncClient, logged_in_headers: dict, phase: str):
    """`GET /plan` is phase-gated: a read before the planning stage is a 403 (no PM call)."""
    project_id = await _make_plan_project(client, logged_in_headers, phase=phase)
    response = await client.get(f"api/v1/lothal/projects/{project_id}/plan", headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def _link_pm_project(project_id: str, pm_id: str) -> None:
    """Pre-persist the LF→PM mapping so a route reuses it instead of creating one."""
    async with session_scope() as session:
        session.add(PMProjectLink(lf_project_id=UUID(project_id), pm_project_id=UUID(pm_id)))


@pytest.mark.usefixtures("_pm_env")
async def test_get_plan_creates_and_returns_tree(client: AsyncClient, logged_in_headers: dict):
    """In PLAN, GET /plan creates a PM tree on first use, persists the link, and returns nodes + links."""
    project_id = await _make_plan_project(client, logged_in_headers)
    with respx.mock:
        _mock_pm_login()
        # No link row yet → the bridge creates a PM project (server-assigned id).
        create = respx.post(f"{PM_BASE}/api/projects").mock(
            return_value=httpx.Response(201, json={"id": PM_ID_CREATED, "name": project_id})
        )
        respx.get(f"{PM_BASE}/api/projects/{PM_ID_CREATED}/nodes").mock(
            return_value=httpx.Response(
                200,
                json=[{"id": "n1", "parent_id": None, "kind": "app", "state": "draft", "name": "Root", "depth": 0}],
            )
        )
        respx.get(f"{PM_BASE}/api/projects/{PM_ID_CREATED}/links").mock(return_value=httpx.Response(200, json=[]))
        response = await client.get(f"api/v1/lothal/projects/{project_id}/plan", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["plan_id"] == PM_ID_CREATED
    assert [n["id"] for n in body["nodes"]] == ["n1"]
    assert body["links"] == []
    assert create.called
    # The mapping was persisted, so a later call reuses it (create-on-first-use).
    async with session_scope() as session:
        link = await session.get(PMProjectLink, UUID(project_id))
        assert link is not None
        assert str(link.pm_project_id) == PM_ID_CREATED


@pytest.mark.usefixtures("_pm_env")
async def test_get_plan_reuses_existing_tree(client: AsyncClient, logged_in_headers: dict):
    """A persisted link is reused: the bridge resolves the PM id from it, never re-creating."""
    project_id = await _make_plan_project(client, logged_in_headers)
    await _link_pm_project(project_id, PM_ID_EXISTING)
    with respx.mock:
        _mock_pm_login()
        create = respx.post(f"{PM_BASE}/api/projects").mock(
            return_value=httpx.Response(201, json={"id": "should-not-be-used", "name": "x"})
        )
        respx.get(f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/nodes").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/links").mock(return_value=httpx.Response(200, json=[]))
        response = await client.get(f"api/v1/lothal/projects/{project_id}/plan", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["plan_id"] == PM_ID_EXISTING
    assert not create.called  # the persisted link was reused


@pytest.mark.usefixtures("_pm_env")
async def test_create_plan_node_bridges_to_pm(client: AsyncClient, logged_in_headers: dict):
    """POST /plan/nodes forwards the body to the PM service and returns its node."""
    project_id = await _make_plan_project(client, logged_in_headers)
    await _link_pm_project(project_id, PM_ID_EXISTING)
    with respx.mock:
        _mock_pm_login()
        create = respx.post(f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/nodes").mock(
            return_value=httpx.Response(201, json={"id": "n2", "kind": "component", "state": "draft", "name": "Auth"})
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/plan/nodes",
            json={"kind": "component", "name": "Auth"},
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == "n2"
    assert create.called


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PROTOTYPE", "CODE_GENERATION", "DONE"])
async def test_plan_write_rejected_outside_plan(client: AsyncClient, logged_in_headers: dict, phase: str):
    """The tree is editable only during PLAN: a create-node in any other phase is a 409 (no PM call)."""
    project_id = await _make_plan_project(client, logged_in_headers, phase=phase)
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/plan/nodes",
        json={"kind": "component", "name": "Auth"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_approve_plan_advances_to_code(client: AsyncClient, logged_in_headers: dict):
    """Approving the plan advances PLAN → CODE_GENERATION (the PM tree stays the source of truth)."""
    project_id = await _make_plan_project(client, logged_in_headers)
    response = await client.post(f"api/v1/lothal/projects/{project_id}/plan/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"phase": "CODE_GENERATION"}
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        assert project.phase == "CODE_GENERATION"


@pytest.mark.parametrize("phase", ["ARCHITECTURE", "PROTOTYPE", "CODE_GENERATION", "DONE"])
async def test_approve_plan_rejected_outside_plan(client: AsyncClient, logged_in_headers: dict, phase: str):
    """Approve is only valid in PLAN; any other phase is a 409 and a no-op."""
    project_id = await _make_plan_project(client, logged_in_headers, phase=phase)
    response = await client.post(f"api/v1/lothal/projects/{project_id}/plan/approve", headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == phase


@pytest.mark.usefixtures("_pm_env")
async def test_plan_maps_pm_failure_to_502(client: AsyncClient, logged_in_headers: dict):
    """A reachable-but-unhappy PM service surfaces as a 502, not a 500."""
    project_id = await _make_plan_project(client, logged_in_headers)
    with respx.mock:
        _mock_pm_login()
        # First PM call on a fresh project is the create (no link row yet).
        respx.post(f"{PM_BASE}/api/projects").mock(return_value=httpx.Response(500, json={"detail": "boom"}))
        response = await client.get(f"api/v1/lothal/projects/{project_id}/plan", headers=logged_in_headers)
    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.usefixtures("_pm_env")
async def test_ensure_pm_project_race_adopts_winner_and_deletes_orphan(client: AsyncClient, logged_in_headers: dict):
    """A lost create race: `_ensure_pm_project` adopts the winner's link and deletes its orphan PM project.

    Simulates the race deterministically — the fake client's ``create_project``
    commits a competing link row (as a concurrent replica would) *between* the
    initial lookup miss and our own insert, so the insert hits the primary-key
    conflict and the recovery path runs.
    """
    from langflow.api.v1.lothal import _ensure_pm_project

    project_id = await _make_plan_project(client, logged_in_headers)
    winner_pm_id = "33333333-3333-3333-3333-333333333333"
    loser_pm_id = "44444444-4444-4444-4444-444444444444"

    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))

        class _RacingPM:
            """A PM client whose `create_project` lands a competing link first.

            Flushing the winner on the *same* session before our own insert is the
            deterministic, dialect-agnostic stand-in for a concurrent replica whose
            link committed between our lookup miss and our insert — it forces the
            primary-key conflict the recovery path is written for.
            """

            def __init__(self) -> None:
                self.deleted: list[str] = []

            async def create_project(self, name: str) -> dict:
                session.add(PMProjectLink(lf_project_id=project.id, pm_project_id=UUID(winner_pm_id)))
                await session.flush()
                return {"id": loser_pm_id, "name": name}

            async def delete_project(self, pm_id: str) -> None:
                self.deleted.append(pm_id)

        pm = _RacingPM()
        resolved = await _ensure_pm_project(session, project, pm)

    assert resolved == winner_pm_id  # the winner's link is adopted
    assert pm.deleted == [loser_pm_id]  # our orphan PM project is cleaned up
    async with session_scope() as session:
        link = await session.get(PMProjectLink, UUID(project_id))
        assert str(link.pm_project_id) == winner_pm_id


async def test_plan_503_when_pm_base_url_blank(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """A misconfigured bridge (blank base URL) is a 503, mirroring `_od_error_to_http`'s config split."""
    project_id = await _make_plan_project(client, logged_in_headers)
    monkeypatch.setenv("LOTHAL_PM_BASE_URL", "")
    response = await client.get(f"api/v1/lothal/projects/{project_id}/plan", headers=logged_in_headers)
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# Every plan route, with a representative body. `{nid}` / `{tid}` are random UUIDs:
# they never matter because the ownership check fails first (before any PM call),
# which is exactly the IDOR invariant under test. Keep this in lockstep with the
# `…/plan/*` routers in `api/v1/lothal.py`.
def _all_plan_routes(project_id: str) -> list[tuple[str, str, dict | None]]:
    base = f"api/v1/lothal/projects/{project_id}/plan"
    nid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    return [
        ("GET", base, None),
        ("POST", f"{base}/nodes", {"kind": "component", "name": "x"}),
        ("GET", f"{base}/nodes/{nid}", None),
        ("PATCH", f"{base}/nodes/{nid}/contract", {"assumptions": [], "guarantees": []}),
        ("POST", f"{base}/nodes/{nid}/ratify", None),
        ("GET", f"{base}/links", None),
        ("POST", f"{base}/links", {"source_id": nid, "target_id": tid, "link_type": "derives_from"}),
        ("GET", f"{base}/activity", None),
        ("POST", f"{base}/nodes/{nid}/move", {"new_parent_id": None}),
        ("PATCH", f"{base}/nodes/{nid}/criteria", {"criteria": []}),
        ("POST", f"{base}/nodes/{nid}/transition", {"target": "draft"}),
        ("GET", f"{base}/nodes/{nid}/events", None),
        ("GET", f"{base}/nodes/{nid}/dependencies", None),
        ("GET", f"{base}/nodes/{nid}/tests", None),
        ("POST", f"{base}/nodes/{nid}/tests", {"scope": "unit", "spec": "x"}),
        ("POST", f"{base}/nodes/{nid}/tests/{tid}/runs", {"status": "pass"}),
        ("GET", f"{base}/dag.svg", None),
        ("POST", f"{base}/approve", None),
    ]


@pytest.mark.security
@pytest.mark.usefixtures("_pm_env")
async def test_every_plan_route_404s_for_unowned_project_without_touching_pm(
    client: AsyncClient, logged_in_headers: dict, user_two
):
    """IDOR guard, exhaustive: EVERY plan route 404s another user's project *before* the bridge.

    All Langflow users' PM trees live under the one bridge service account, so the
    Langflow-side ownership check is the *only* thing separating users on the plan
    tree — a single unguarded route is a full cross-user read/write IDOR. This
    hits all 18 routes against a project owned by `user_two` and asserts (a) each
    is a 404 (never 403/409, which would confirm the project exists) and (b) the PM
    service was never contacted — respx has no routes registered, so any bridge
    call would raise instead of returning, and `respx.calls` must stay empty.
    """
    async with session_scope() as session:
        foreign = Project(name="Theirs", user_id=user_two.id, phase="PLAN")
        session.add(foreign)
        await session.flush()
        foreign_pk = foreign.id

    try:
        with respx.mock:  # no routes registered → any PM call raises, and calls stay empty
            for method, path, body in _all_plan_routes(str(foreign_pk)):
                response = await client.request(method, path, json=body, headers=logged_in_headers)
                assert response.status_code == status.HTTP_404_NOT_FOUND, (method, path, response.status_code)
            assert respx.calls.call_count == 0, "ownership must be checked before the PM bridge is touched"
    finally:
        async with session_scope() as session:
            leftover = await session.get(Project, foreign_pk)
            if leftover:
                await session.delete(leftover)


@pytest.mark.security
async def test_every_plan_route_requires_auth(client: AsyncClient):
    """No plan route is reachable without authentication (401/403, never 2xx)."""
    for method, path, body in _all_plan_routes(PROJECT_ID):
        response = await client.request(method, path, json=body)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ), (method, path, response.status_code)


# --- code-generation bridge (BYOK launch + status) ---------------------------
# The launch flow attaches the user's OWN subscription token to the PM node, then
# drives ratified→in_progress. It also exercises PMClient.attach_byok / transition /
# get_codegen through the bridge.

_CODEGEN_NODE_ID = "33333333-3333-3333-3333-333333333333"


@pytest.mark.usefixtures("_pm_env")
async def test_launch_codegen_attaches_byok_transitions_and_returns_job(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Launch attaches the user's token to the PM node, transitions to in_progress, and returns the job."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-user-key")
    project_id = await _make_plan_project(client, logged_in_headers, phase="CODE_GENERATION")
    await _link_pm_project(project_id, PM_ID_EXISTING)
    base = f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/nodes/{_CODEGEN_NODE_ID}"
    with respx.mock:
        _mock_pm_login()
        byok = respx.post(f"{base}/byok").mock(
            return_value=httpx.Response(
                200, json={"node_id": _CODEGEN_NODE_ID, "key_kind": "claude_oauth", "stored": True}
            )
        )
        transition = respx.post(f"{base}/transition").mock(
            return_value=httpx.Response(200, json={"state": "in_progress"})
        )
        codegen = respx.get(f"{base}/codegen").mock(return_value=httpx.Response(200, json={"state": "queued"}))
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/plan/nodes/{_CODEGEN_NODE_ID}/codegen/launch",
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["state"] == "queued"
    assert byok.called
    assert transition.called
    assert codegen.called
    # The resolved token is forwarded to PM's byok endpoint (encrypted at rest there)...
    sent = json.loads(byok.calls.last.request.content)
    assert sent["token"] == "sk-ant-oat-user-key"  # noqa: S105
    assert sent["key_kind"] == "claude_oauth"
    # ...and the launch drives ratified→in_progress, but the token never returns to the browser.
    assert json.loads(transition.calls.last.request.content)["target"] == "in_progress"
    assert "sk-ant-oat-user-key" not in response.text


async def test_launch_codegen_400_without_token(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """No per-user variable and no server token → 400, and the PM bridge is never touched."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    project_id = await _make_plan_project(client, logged_in_headers, phase="CODE_GENERATION")
    with respx.mock:  # no routes registered → any PM call would raise
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/plan/nodes/{_CODEGEN_NODE_ID}/codegen/launch",
            headers=logged_in_headers,
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "CLAUDE_CODE_OAUTH_TOKEN" in response.json()["detail"]
    assert respx.calls.call_count == 0


@pytest.mark.parametrize("phase", ["PROTOTYPE", "PLAN", "DONE"])
async def test_launch_codegen_409_outside_code_phase(
    client: AsyncClient, logged_in_headers: dict, monkeypatch, phase: str
):
    """Launch is only valid in CODE_GENERATION; any other phase is a 409 before any token/PM work."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-user-key")
    project_id = await _make_plan_project(client, logged_in_headers, phase=phase)
    with respx.mock:
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/plan/nodes/{_CODEGEN_NODE_ID}/codegen/launch",
            headers=logged_in_headers,
        )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert respx.calls.call_count == 0


@pytest.mark.usefixtures("_pm_env")
async def test_launch_codegen_maps_pm_failure_to_502(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """A PM failure while attaching the key surfaces as a 502 (bridge error mapping)."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-user-key")
    project_id = await _make_plan_project(client, logged_in_headers, phase="CODE_GENERATION")
    await _link_pm_project(project_id, PM_ID_EXISTING)
    with respx.mock:
        _mock_pm_login()
        respx.post(f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/nodes/{_CODEGEN_NODE_ID}/byok").mock(
            return_value=httpx.Response(500, json={"detail": "boom"})
        )
        response = await client.post(
            f"api/v1/lothal/projects/{project_id}/plan/nodes/{_CODEGEN_NODE_ID}/codegen/launch",
            headers=logged_in_headers,
        )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.usefixtures("_pm_env")
async def test_get_codegen_status_bridges_to_pm(client: AsyncClient, logged_in_headers: dict):
    """GET /codegen returns the node's current code-gen run from PM (visible in PLAN and later)."""
    project_id = await _make_plan_project(client, logged_in_headers, phase="CODE_GENERATION")
    await _link_pm_project(project_id, PM_ID_EXISTING)
    with respx.mock:
        _mock_pm_login()
        codegen = respx.get(f"{PM_BASE}/api/projects/{PM_ID_EXISTING}/nodes/{_CODEGEN_NODE_ID}/codegen").mock(
            return_value=httpx.Response(200, json={"state": "running", "attempt": 1})
        )
        response = await client.get(
            f"api/v1/lothal/projects/{project_id}/plan/nodes/{_CODEGEN_NODE_ID}/codegen",
            headers=logged_in_headers,
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == "running"
    assert codegen.called
