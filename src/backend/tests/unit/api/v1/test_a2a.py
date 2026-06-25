"""Integration tests for the A2A endpoints (agent card + JSON-RPC message/send).

The routes are public and gated behind LANGFLOW_A2A_ENABLED (default off). These
tests drive the real endpoints against the test DB: flows and folders are created
directly via session_scope, the server flag is toggled on the live settings
object, the served card is revalidated against the a2a-sdk model, and message/send
runs a real echo flow through the v2 surface.
"""

import uuid
from pathlib import Path

import langflow
import orjson
import pytest
from a2a.compat.v0_3 import types as a2a_types
from httpx import AsyncClient
from langflow.helpers.flow import json_schema_from_flow
from langflow.services.database.models import Folder
from langflow.services.database.models.flow.model import Flow, FlowType
from langflow.services.deps import session_scope
from lfx.services.deps import get_settings_service

_STARTERS = Path(langflow.__file__).parent / "initial_setup" / "starter_projects"


def _card_url(flow_id) -> str:
    return f"api/v1/a2a/{flow_id}/.well-known/agent-card.json"


async def _create_flow(
    user_id,
    *,
    data,
    flow_type=FlowType.AGENT,
    a2a_enabled=True,
    folder_id=None,
    overrides=None,
):
    async with session_scope() as session:
        flow = Flow(
            name=f"a2a-flow-{uuid.uuid4().hex[:8]}",
            data=data,
            user_id=user_id,
            flow_type=flow_type,
            a2a_enabled=a2a_enabled,
            folder_id=folder_id,
            a2a_card_overrides=overrides,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        return flow.id


async def _create_folder(user_id, *, auth_settings):
    async with session_scope() as session:
        folder = Folder(
            name=f"a2a-folder-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            auth_settings=auth_settings,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder.id


@pytest.fixture
def a2a_flag_on(client):  # noqa: ARG001 - client ensures settings are built first
    """Turn the server A2A flag on for the duration of a test, then restore."""
    settings = get_settings_service().settings
    original = settings.a2a_enabled
    settings.a2a_enabled = True
    yield
    settings.a2a_enabled = original


@pytest.fixture
def flow_data():
    """Real, current-format agent flow data (has an input node for the skill schema)."""
    return orjson.loads((_STARTERS / "Simple Agent.json").read_bytes())["data"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_get_agent_card_returns_valid_card(client: AsyncClient, active_user, flow_data):
    """An agent-typed, a2a_enabled flow serves a spec-valid card carrying the flow schema."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    assert body["url"].endswith(f"/api/v1/a2a/{flow_id}/jsonrpc")
    assert body["protocolVersion"] == "0.3.0"
    assert body["preferredTransport"] == "JSONRPC"

    # The card (minus the non-model inputSchema key) revalidates against the SDK model.
    skill = {k: v for k, v in body["skills"][0].items() if k != "inputSchema"}
    a2a_types.AgentCard.model_validate({**body, "skills": [skill]})

    input_schema = body["skills"][0]["inputSchema"]
    assert input_schema["type"] == "object"
    assert input_schema["properties"]["session_id"]["type"] == "string"

    # The published schema matches what json_schema_from_flow computes directly.
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert input_schema == json_schema_from_flow(flow)


@pytest.mark.usefixtures("a2a_flag_on")
async def test_capabilities_advertised_false(client: AsyncClient, active_user, flow_data):
    """Streaming and pushNotifications must be present and explicitly false."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["capabilities"] == {"streaming": False, "pushNotifications": False}


@pytest.mark.usefixtures("a2a_flag_on")
async def test_workflow_flow_returns_404(client: AsyncClient, active_user, flow_data):
    """A workflow-typed flow is not an agent, so the card 404s even with a2a_enabled."""
    flow_id = await _create_flow(active_user.id, data=flow_data, flow_type=FlowType.WORKFLOW)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_agent_flow_a2a_disabled_returns_404(client: AsyncClient, active_user, flow_data):
    """An agent flow with a2a_enabled=False 404s."""
    flow_id = await _create_flow(active_user.id, data=flow_data, a2a_enabled=False)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_agent_flow_a2a_none_returns_404(client: AsyncClient, active_user, flow_data):
    """An agent flow with a2a_enabled=None 404s (covers the bool|None branch)."""
    flow_id = await _create_flow(active_user.id, data=flow_data, a2a_enabled=None)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_missing_flow_returns_404(client: AsyncClient):
    """A random flow id 404s."""
    response = await client.get(_card_url(uuid.uuid4()))

    assert response.status_code == 404


async def test_flag_off_returns_404(client: AsyncClient, active_user, flow_data):
    """A valid agent+enabled flow 404s when the server flag is off (no a2a_flag_on)."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_card_overrides_merged(client: AsyncClient, active_user, flow_data):
    """a2a_card_overrides override the editable bits of the card."""
    overrides = {"name": "Custom Agent", "description": "Custom desc", "version": "9.9.9", "tags": ["x", "y"]}
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides=overrides)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["name"] == "Custom Agent"
    assert body["description"] == "Custom desc"
    assert body["version"] == "9.9.9"
    assert body["skills"][0]["name"] == "Custom Agent"
    assert body["skills"][0]["tags"] == ["x", "y"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_defaults_when_no_overrides(client: AsyncClient, active_user, flow_data):
    """Without overrides the card falls back to the flow name and the langflow version."""
    from langflow.utils.version import get_version_info

    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert body["name"] == flow.name
    assert body["version"] == get_version_info()["version"]
    assert body["skills"][0]["tags"] == ["langflow"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_security_schemes_apikey(client: AsyncClient, active_user, flow_data):
    """A folder with apikey auth reflects an x-api-key security scheme onto the card."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "apikey"})
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=folder_id)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["securitySchemes"] == {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "x-api-key",
            "description": "API key passed in the x-api-key header.",
        }
    }
    assert body["security"] == [{"apiKey": []}]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_no_security_for_oauth_folder(client: AsyncClient, active_user, flow_data):
    """OAuth is out of F2 scope, so no security is advertised."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "oauth"})
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=folder_id)

    body = (await client.get(_card_url(flow_id))).json()

    assert "securitySchemes" not in body
    assert "security" not in body


@pytest.mark.usefixtures("a2a_flag_on")
async def test_no_security_for_folderless_flow(client: AsyncClient, active_user, flow_data):
    """A flow without a folder advertises no security."""
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=None)

    body = (await client.get(_card_url(flow_id))).json()

    assert "securitySchemes" not in body
    assert "security" not in body


@pytest.mark.usefixtures("a2a_flag_on")
async def test_unbuildable_flow_serves_empty_input_schema(client: AsyncClient, active_user):
    """An agent flow with empty/unbuildable data serves a valid card with an empty input schema, not a 500."""
    flow_id = await _create_flow(active_user.id, data={})

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    assert body["skills"][0]["inputSchema"] == {"type": "object", "properties": {}, "required": []}


@pytest.mark.usefixtures("a2a_flag_on")
async def test_malformed_overrides_fall_back_to_defaults(client: AsyncClient, active_user, flow_data):
    """Wrong-typed override values are ignored (no 500); the card falls back to defaults."""
    from langflow.utils.version import get_version_info

    overrides = {"name": 123, "version": 9, "tags": "billing", "examples": [1, 2]}
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides=overrides)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert body["name"] == flow.name
    assert body["version"] == get_version_info()["version"]
    assert body["skills"][0]["tags"] == ["langflow"]
    assert "examples" not in body["skills"][0]


# --- JSON-RPC message/send + tasks/get -------------------------------------

_ECHO_FLOW = Path(__file__).parents[3] / "data" / "chat_echo_no_llm.json"


@pytest.fixture
def echo_flow_data():
    """ChatInput -> ChatOutput echo flow (no LLM); a sync run returns input_value verbatim."""
    return orjson.loads(_ECHO_FLOW.read_bytes())["data"]


def _text_message(text, message_id="m1"):
    return {"message": {"role": "user", "parts": [{"kind": "text", "text": text}], "messageId": message_id}}


async def _jsonrpc(client: AsyncClient, flow_id, method, params, rpc_id=1):
    return await client.post(
        f"api/v1/a2a/{flow_id}/jsonrpc",
        json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
    )


@pytest.mark.usefixtures("a2a_flag_on")
async def test_message_send_runs_flow_and_returns_completed_task(client: AsyncClient, active_user, echo_flow_data):
    """message/send runs the flow through the v2 surface and returns a completed Task with a text artifact."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)

    response = await _jsonrpc(client, flow_id, "message/send", _text_message("hello a2a"))

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["kind"] == "task"
    assert result["status"]["state"] == "completed"
    assert result["artifacts"][0]["parts"][0]["text"] == "hello a2a"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_tasks_get_returns_prior_task(client: AsyncClient, active_user, echo_flow_data):
    """tasks/get reads back the Task a prior message/send created (durable DB-backed store)."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    sent = (await _jsonrpc(client, flow_id, "message/send", _text_message("remember me"))).json()["result"]
    task_id = sent["id"]

    got = (await _jsonrpc(client, flow_id, "tasks/get", {"id": task_id})).json()["result"]

    assert got["kind"] == "task"
    assert got["id"] == task_id
    assert got["status"]["state"] == "completed"
    assert got["artifacts"][0]["parts"][0]["text"] == "remember me"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_jsonrpc_dispatches_by_flow_id(client: AsyncClient, active_user, echo_flow_data):
    """The same shared handler routes each request to the flow named in the path.

    Same input to two different flows yields different intrinsic outcomes (a
    buildable echo completes; an unbuildable flow fails), so the path's flow_id
    really selects the flow rather than always running one of them.
    """
    good = await _create_flow(active_user.id, data=echo_flow_data)
    broken = await _create_flow(active_user.id, data={})

    good_result = (await _jsonrpc(client, good, "message/send", _text_message("ping"))).json()["result"]
    broken_result = (await _jsonrpc(client, broken, "message/send", _text_message("ping"))).json()["result"]

    assert good_result["status"]["state"] == "completed"
    assert good_result["artifacts"][0]["parts"][0]["text"] == "ping"
    assert broken_result["status"]["state"] == "failed"
    assert broken_result["status"]["message"]["parts"][0]["text"]


async def test_jsonrpc_flag_off_returns_404(client: AsyncClient, active_user, echo_flow_data):
    """With the server flag off, the JSON-RPC route 404s before any dispatch."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)

    response = await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_jsonrpc_non_agent_or_disabled_returns_404(client: AsyncClient, active_user, echo_flow_data):
    """Workflow-typed and a2a-disabled flows 404 on the JSON-RPC route, like the card route."""
    workflow_id = await _create_flow(active_user.id, data=echo_flow_data, flow_type=FlowType.WORKFLOW)
    disabled_id = await _create_flow(active_user.id, data=echo_flow_data, a2a_enabled=False)

    assert (await _jsonrpc(client, workflow_id, "message/send", _text_message("hi"))).status_code == 404
    assert (await _jsonrpc(client, disabled_id, "message/send", _text_message("hi"))).status_code == 404
    assert (await _jsonrpc(client, uuid.uuid4(), "message/send", _text_message("hi"))).status_code == 404


def _response(*, output, outputs=None):
    from lfx.schema.workflow import JobStatus, WorkflowExecutionResponse

    return WorkflowExecutionResponse(flow_id="f", status=JobStatus.COMPLETED, output=output, outputs=outputs or {})


def test_answer_texts_resolves_each_output_reason():
    """SINGLE keeps its text (even ""); MULTIPLE recovers every text channel; NONE is empty."""
    from langflow.api.v1.a2a_executor import _answer_texts
    from lfx.schema.workflow import ComponentOutput, JobStatus, OutputReason, WorkflowOutput

    single = _response(output=WorkflowOutput(reason=OutputReason.SINGLE, text=""))
    assert _answer_texts(single) == [""]

    multi = _response(
        output=WorkflowOutput(reason=OutputReason.MULTIPLE),
        outputs={
            "a": ComponentOutput(type="message", status=JobStatus.COMPLETED, content="x"),
            "b": ComponentOutput(type="text", status=JobStatus.COMPLETED, content="y"),
        },
    )
    assert _answer_texts(multi) == ["x", "y"]

    none = _response(output=WorkflowOutput(reason=OutputReason.NONE))
    assert _answer_texts(none) == []


# --- durable task store ----------------------------------------------------


@pytest.mark.usefixtures("client")
async def test_durable_store_roundtrips_across_instances():
    """A task saved by one store instance is read back by a fresh instance.

    Two independent DurableTaskStore instances share only the DB, so this is the
    survives-restart / visible-across-workers property the in-memory store lacked.
    """
    from a2a.server.context import ServerCallContext
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1.a2a import DurableTaskStore

    task_id = str(uuid.uuid4())
    task = pb.Task(
        id=task_id,
        context_id="c1",
        status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_COMPLETED),
    )
    ctx = ServerCallContext()  # default UnauthenticatedUser -> owner ""

    await DurableTaskStore().save(task, ctx)
    got = await DurableTaskStore().get(task_id, ctx)

    assert got is not None
    assert got.id == task_id
    assert got.context_id == "c1"
    assert got.status.state == pb.TaskState.TASK_STATE_COMPLETED

    # Pin durability to the DB: this row must exist in the table, so the test fails if
    # the store ever stops being DB-backed (composite PK is (id, owner), owner "").
    from langflow.services.database.models import A2ATask
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        assert await session.get(A2ATask, (task_id, "")) is not None


@pytest.mark.usefixtures("client")
async def test_durable_store_is_owner_scoped():
    """get() is scoped to the saving owner; a different owner doesn't see the task."""
    from a2a.auth.user import User
    from a2a.server.context import ServerCallContext
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1.a2a import DurableTaskStore

    class _NamedUser(User):
        @property
        def is_authenticated(self) -> bool:
            return True

        @property
        def user_name(self) -> str:
            return "someone-else"

    task_id = str(uuid.uuid4())
    task = pb.Task(id=task_id, status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_SUBMITTED))

    await DurableTaskStore().save(task, ServerCallContext())  # owner ""

    # Positive control: the saving owner sees it, so a None below is the owner filter,
    # not a failed save.
    hit = await DurableTaskStore().get(task_id, ServerCallContext())
    assert hit is not None
    assert hit.id == task_id

    miss = await DurableTaskStore().get(task_id, ServerCallContext(user=_NamedUser()))
    assert miss is None


def _pg_url(raw: str) -> str:
    """Strip any driver suffix to a bare ``postgresql://`` URL.

    DatabaseService then applies langflow's own async driver (psycopg), which is the
    production path; forcing ``+asyncpg`` here breaks because the postgres connect args
    (e.g. ``prepare_threshold``) are psycopg-specific.
    """
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql+psycopg2://"):
        if raw.startswith(prefix):
            return "postgresql://" + raw[len(prefix) :]
    if raw.startswith("postgres://"):
        return "postgresql://" + raw[len("postgres://") :]
    return raw


@pytest.fixture(params=["sqlite", "postgres"])
async def a2a_migrated_db(request, tmp_path, monkeypatch):
    """Bind ``session_scope`` to a real, migration-built DB and yield its URL.

    Runs the production Alembic migrations (not ``create_all``) so the ``a2a_tasks``
    DDL — and its JSONB ``task`` column on Postgres — is actually exercised. SQLite
    always runs; Postgres runs only when ``LANGFLOW_TEST_DATABASE_URI`` is set (CI sets
    it), else the param skips.

    ponytail: mirrors the background_execution real_services harness fixture, kept local
    so this slice doesn't refactor that package's conftest. ``LANGFLOW_DATABASE_URL`` is
    set (not just the settings attribute) because the settings validator lets that env
    var win, so a bare attribute assignment would silently fall back to the default DB.
    """
    import contextlib
    import os

    from langflow.services.database.factory import DatabaseServiceFactory
    from langflow.services.deps import get_settings_service
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    if request.param == "sqlite":
        url = f"sqlite+aiosqlite:///{tmp_path}/a2a_real.db"
    else:
        raw = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not raw:
            pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
        url = _pg_url(raw)

    manager = get_service_manager()
    settings_service = get_settings_service()
    original_db = manager.services.pop(ServiceType.DATABASE_SERVICE, None)

    monkeypatch.setenv("LANGFLOW_DATABASE_URL", url)  # the validator honors this over the attribute
    settings_service.settings.database_url = url  # re-runs the validator, now picking up the env
    db_service = DatabaseServiceFactory().create(settings_service)
    manager.services[ServiceType.DATABASE_SERVICE] = db_service  # run_migrations()/session_scope resolve here
    try:
        await db_service.run_migrations()
        yield url
    finally:
        manager.services.pop(ServiceType.DATABASE_SERVICE, None)
        with contextlib.suppress(Exception):
            await db_service.teardown()
        if original_db is not None:
            manager.services[ServiceType.DATABASE_SERVICE] = original_db


@pytest.mark.real_services
@pytest.mark.usefixtures("a2a_migrated_db")
async def test_durable_store_roundtrips_on_real_migrated_db():
    """The durable store round-trips a Task on a real migration-built DB (sqlite + postgres).

    Each ``DurableTaskStore()`` is a fresh instance sharing only the DB, so this also
    proves the cross-instance / survives-restart property on the real engine, and that
    the proto<->JSON round-trip survives the JSONB column on Postgres.
    """
    from a2a.auth.user import User
    from a2a.server.context import ServerCallContext
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1.a2a import DurableTaskStore

    task_id = str(uuid.uuid4())
    task = pb.Task(
        id=task_id,
        context_id="ctx-1",
        status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_COMPLETED),
    )
    ctx = ServerCallContext()

    await DurableTaskStore().save(task, ctx)
    got = await DurableTaskStore().get(task_id, ctx)

    assert got is not None
    assert got.id == task_id
    assert got.context_id == "ctx-1"
    assert got.status.state == pb.TaskState.TASK_STATE_COMPLETED

    class _Other(User):
        @property
        def is_authenticated(self) -> bool:
            return True

        @property
        def user_name(self) -> str:
            return "other"

    assert await DurableTaskStore().get(task_id, ServerCallContext(user=_Other())) is None
