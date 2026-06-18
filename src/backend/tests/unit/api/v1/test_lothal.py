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

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import lothal as lothal_api
from langflow.lothal.d2_compile import D2CompilerUnavailableError
from langflow.lothal.engines import clarification as clarification_engine
from langflow.lothal.engines import d2_gate
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
    ("POST", "api/v1/lothal/projects/{project_id}/diagram/save", {"nodes": [], "edges": []}),
    ("POST", "api/v1/lothal/projects/{project_id}/diagram/approve", None),
    ("GET", "api/v1/lothal/projects/{project_id}/code", None),
    ("GET", "api/v1/lothal/projects/{project_id}/download", None),
]

# Every remaining stub is project-scoped, so each resolves ownership before
# stubbing.
PROJECT_SCOPED_STUB_TEMPLATES = [t for t in STUB_TEMPLATES if "{project_id}" in t[1]]

STUBBED_ENDPOINTS = [(m, p.format(project_id=PROJECT_ID), b) for m, p, b in STUB_TEMPLATES]

# The routes that have gone live: project CRUD (B.2), the LLM debug round-trip
# (0.4), chat routing + message history (1.2), the PRD read (1.3), and the
# diagram read (2.3). Still require auth, but no longer return `501`.
LIVE_ENDPOINTS = [
    ("POST", "api/v1/lothal/projects/", {"name": "My App"}),
    ("GET", "api/v1/lothal/projects/", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("DELETE", f"api/v1/lothal/projects/{PROJECT_ID}", None),
    ("POST", f"api/v1/lothal/projects/{PROJECT_ID}/chat", {"content": "hi"}),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/messages", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/prd", None),
    ("GET", f"api/v1/lothal/projects/{PROJECT_ID}/diagram", None),
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
    # routes that have gone live (chat, debug, prd, diagram) no longer advertise it.
    assert "501" in paths["/api/v1/lothal/projects/{project_id}/diagram/save"]["post"]["responses"]
    assert "501" not in paths["/api/v1/lothal/projects/{project_id}/diagram"]["get"]["responses"]
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
    # list. Graphs are seeded straight into the DB: the save endpoint that
    # will write them (story 3.2) is still a stub.
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
    """Backlog acceptance for the clarification turn lifecycle.

    Three no-signal turns yield 6 messages with the phase unchanged; one
    `[CLARITY_REACHED]` turn advances to DIAGRAM_GENERATION, stores the PRD, and
    strips the control token.
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

    # The clarity turn transitions the project and stores the PRD with the token stripped.
    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat", json={"content": "looks good"}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["phase"] == "CLARIFICATION"  # the turn ran under CLARIFICATION
    assert reply["suggestions"] == []
    assert "[CLARITY_REACHED]" not in reply["content"]  # control token stripped
    assert "Overview" in reply["content"]

    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "DIAGRAM_GENERATION"  # phase persists on transition
    assert project["prd_content"] is not None
    assert "[CLARITY_REACHED]" not in project["prd_content"]
    assert "Overview" in project["prd_content"]


# --- Diagram generation (Story 2.1, re-pointed to D2 in Epic D.2) -------------


def _diagram_reply() -> str:
    """A D2 sequence diagram in the shape the generator now emits (Epic D.2)."""
    return "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok\nuser -> api: poll"


async def test_diagram_generation_turn_persists_graph_and_hands_off_to_refinement(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Backlog acceptance for Epic D.2 + the D.8 hand-off (fake LLM).

    A chat turn while the project is in DIAGRAM_GENERATION runs the generator
    engine for real (only the model call is faked): the injected D2 source is
    persisted verbatim to `lothal_project.diagram_d2`, the legacy `diagram_json`
    stays null, and — having drafted the first diagram — the project advances to
    DIAGRAM_REFINEMENT (D.8) so the next turn refines it. Both messages are still
    stamped with the phase the turn ran under (DIAGRAM_GENERATION).
    """
    project_id = await _create_chat_project(client, logged_in_headers)

    # Precondition: the project has left CLARIFICATION (PRD written, phase moved).
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "DIAGRAM_GENERATION"
        session.add(project)

    async def fake_call_llm(_messages, **_kwargs):
        return _diagram_reply()

    monkeypatch.setattr(d2_gate, "call_llm", fake_call_llm)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "generate the diagram"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["role"] == "ASSISTANT"
    assert reply["phase"] == "DIAGRAM_GENERATION"  # the turn ran under this phase
    assert reply["suggestions"] == []
    assert "3 interactions" in reply["content"]  # text grounded in the generated D2

    # The diagram lands in `diagram_d2` verbatim (the legacy `diagram_json` stays
    # null) and the project advances to DIAGRAM_REFINEMENT for the next turn (D.8).
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "DIAGRAM_REFINEMENT"
    assert project["diagram_json"] is None
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.diagram_d2 == _diagram_reply()


async def test_diagram_generation_empty_reply_is_502_and_rolls_back(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """An empty D2 reply fails the turn as a bad model round-trip and persists nothing.

    The whole turn is one transaction, so the user message is rolled back too and
    `diagram_d2` stays null — the user can resend cleanly. (Compile-validation
    with a corrective retry is Epic D.3.)
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "DIAGRAM_GENERATION"
        session.add(project)

    async def fake_call_llm(_messages, **_kwargs):
        return "   \n  "  # empty after fences/whitespace are stripped

    monkeypatch.setattr(d2_gate, "call_llm", fake_call_llm)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "generate the diagram"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY

    # Nothing persisted: no diagram, and the user turn rolled back with it.
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.diagram_d2 is None
        assert stored.diagram_json is None
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert messages == []


# --- Diagram refinement (Epic D.8) --------------------------------------------


def _refined_d2() -> str:
    """The updated D2 a refinement turn's (faked) model returns."""
    return "shape: sequence_diagram\nbrowser: Browser\napi: API\n\nbrowser -> api: submit\napi -> browser: ok"


async def test_refinement_turn_updates_d2_and_holds_phase(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Backlog acceptance for Epic D.8 (fake LLM).

    A chat turn while the project is in DIAGRAM_REFINEMENT runs the refinement
    engine for real (only the model call is faked): the turn the model receives
    carries the project's current D2, its PRD, and the anchored element id; the
    model's updated D2 is persisted verbatim to `diagram_d2`, `GET /diagram`
    reflects it, and the project stays in DIAGRAM_REFINEMENT (approval is D.11).
    """
    project_id = await _create_chat_project(client, logged_in_headers)
    seed_d2 = "shape: sequence_diagram\nuser: User\napi: API\n\nuser -> api: submit\napi -> user: ok"
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "DIAGRAM_REFINEMENT"
        project.prd_content = "## Overview\nA todo app for individuals."
        project.diagram_d2 = seed_d2
        session.add(project)

    captured: dict = {}

    async def fake_call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return _refined_d2()

    monkeypatch.setattr(d2_gate, "call_llm", fake_call_llm)

    response = await client.post(
        f"api/v1/lothal/projects/{project_id}/chat",
        json={"content": "rename `user` to Browser"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    reply = response.json()
    assert reply["role"] == "ASSISTANT"
    assert reply["phase"] == "DIAGRAM_REFINEMENT"
    assert reply["suggestions"] == []

    # The refinement turn the model saw carried the current D2, the PRD, and the
    # anchored element id (the D.7 composer serialises it backtick-wrapped).
    composed = captured["messages"][-1]["content"]
    assert "user -> api: submit" in composed  # the current diagram to edit
    assert "A todo app for individuals." in composed  # the PRD
    assert "`user`" in composed  # the referenced element id

    # The updated D2 is persisted and reflected by GET /diagram; the phase holds.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "DIAGRAM_REFINEMENT"
    async with session_scope() as session:
        stored = await session.get(Project, UUID(project_id))
        assert stored.diagram_d2 == _refined_d2()

    diagram = (await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)).json()
    assert diagram["d2"] == _refined_d2()


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
    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=None)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": None, "svg": None}


async def test_diagram_returns_seeded_d2(client: AsyncClient, logged_in_headers: dict, stub_diagram_render):
    """A seeded `diagram_d2` comes back as the D2 source verbatim plus the rendered SVG."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=_SEED_D2)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    # The D2 shape: source text plus the server-rendered SVG (D.6) — no xyflow
    # `nodes`/`edges`.
    assert set(body) == {"d2", "svg"}
    assert body["d2"] == _SEED_D2
    assert body["svg"] == stub_diagram_render


async def test_diagram_readable_in_later_phases(client: AsyncClient, logged_in_headers: dict):
    """The D2 source stays readable through refinement, code generation, and done."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    for phase in ("DIAGRAM_REFINEMENT", "CODE_GENERATION", "DONE"):
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
        await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=raw)
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

    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=_SEED_D2)
    body = (await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)).json()
    assert body["d2"] == _SEED_D2
    assert body["svg"] is not None
    assert "<svg" in body["svg"]

    # Non-compilable source still 200s; the render fails closed to svg: null.
    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2="not valid d2 {{{")
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
    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=_SEED_D2)

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
    await _set_phase_and_d2(UUID(project_id), phase="DIAGRAM_GENERATION", diagram_d2=_SEED_D2)

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": _SEED_D2, "svg": None}


async def test_diagram_legacy_xyflow_only_reads_empty(client: AsyncClient, logged_in_headers: dict):
    """A pre-Epic-D project with only `diagram_json` (no D2) reads as empty until migrated (D.13)."""
    project_id = await _create_chat_project(client, logged_in_headers, name="Diagram")
    async with session_scope() as session:
        project = await session.get(Project, UUID(project_id))
        project.phase = "DIAGRAM_GENERATION"
        project.diagram_json = json.dumps({"nodes": [{"id": "x"}], "edges": []})
        project.diagram_d2 = None

    response = await client.get(f"api/v1/lothal/projects/{project_id}/diagram", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"d2": None, "svg": None}


async def test_diagram_404_for_unowned_project(client: AsyncClient, logged_in_headers: dict, user_two):
    """Ownership is resolved before the phase gate — another user's project 404s, never 403."""
    async with session_scope() as session:
        # Phase set past CLARIFICATION so a 403 can't mask the 404 we're asserting.
        foreign = Project(name="Theirs", user_id=user_two.id, phase="DIAGRAM_GENERATION")
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
    emits `[CLARITY_REACHED]`: the project advances to DIAGRAM_GENERATION, the
    control token is stripped, and `GET /prd` returns the stored summary.
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

    async def has_transitioned() -> bool:
        # A turn's reply is stamped with the phase it ran *under*, so a transition
        # only shows up on the project row — never on `reply["phase"]`.
        project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
        return project["phase"] != "CLARIFICATION"

    transitioned = await has_transitioned()

    # Keep answering until the model reaches clarity (phase moves off CLARIFICATION),
    # falling back to a generic nudge once the canned answers run out.
    answers = iter(_SMOKE_ANSWERS)
    turns = 1
    while not transitioned and turns < _SMOKE_MAX_TURNS:
        answer = next(answers, "That's everything you need — please write the spec now.")
        reply = await send(answer)
        turns += 1
        saw_suggestions = saw_suggestions or bool(reply["suggestions"])
        transitioned = await has_transitioned()

    # Clarity must be reached within the bounded number of turns.
    project = (await client.get(f"api/v1/lothal/projects/{project_id}", headers=logged_in_headers)).json()
    assert project["phase"] == "DIAGRAM_GENERATION", f"never reached clarity in {turns} turns"

    # At least one clarification turn offered tappable suggestions (focused questions).
    assert saw_suggestions, "no clarification turn returned suggestions"

    # The clarity turn's reply is the PRD summary with the control token stripped.
    assert "[CLARITY_REACHED]" not in reply["content"]
    assert reply["suggestions"] == []

    # The PRD is stored and surfaced by `GET /prd`, token-free.
    prd = (await client.get(f"api/v1/lothal/projects/{project_id}/prd", headers=logged_in_headers)).json()
    assert prd["content"], "PRD was not stored on transition"
    assert "[CLARITY_REACHED]" not in prd["content"]
    assert project["prd_content"] == prd["content"]

    # History replays the whole exchange, oldest first, alternating user/assistant.
    messages = (await client.get(f"api/v1/lothal/projects/{project_id}/messages", headers=logged_in_headers)).json()
    assert len(messages) == turns * 2  # each turn = user + assistant
    assert messages[0]["role"] == "USER"
    assert all("[CLARITY_REACHED]" not in m["content"] for m in messages)
