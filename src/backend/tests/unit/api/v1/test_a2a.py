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
async def test_capabilities_advertises_streaming(client: AsyncClient, active_user, flow_data):
    """Streaming and push notifications are both advertised."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["capabilities"] == {"streaming": True, "pushNotifications": True}


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
async def test_override_lists_are_bounded(client: AsyncClient, active_user, flow_data):
    """Free-form override lists are capped so the public card can't be bloated."""
    overrides = {"tags": [f"t{i}" for i in range(200)], "examples": [f"e{i}" for i in range(200)]}
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides=overrides)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    assert len(body["skills"][0]["tags"]) == 50
    assert len(body["skills"][0]["examples"]) == 50


@pytest.mark.usefixtures("a2a_flag_on")
async def test_overlong_string_override_falls_back(client: AsyncClient, active_user, flow_data):
    """An over-long string override is dropped and falls back to the flow default."""
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides={"name": "x" * 5000})

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert body["name"] == flow.name


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


# --- agent registry (owner-scoped listing) ---------------------------------


@pytest.mark.usefixtures("a2a_flag_on")
async def test_list_agents_is_owner_scoped(client: AsyncClient, active_user, logged_in_headers, flow_data):
    """GET /a2a/agents lists only the caller's own agent + a2a_enabled flows, each with a card URL."""
    enabled = await _create_flow(active_user.id, data=flow_data)  # agent + a2a_enabled: included
    await _create_flow(active_user.id, data=flow_data, a2a_enabled=False)  # excluded: a2a disabled
    await _create_flow(active_user.id, data=flow_data, flow_type=FlowType.WORKFLOW)  # excluded: not an agent
    other = await _create_other_user()
    await _create_flow(other, data=flow_data)  # excluded: another user's agent

    resp = await client.get("api/v1/a2a/agents", headers=logged_in_headers)

    assert resp.status_code == 200
    agents = resp.json()
    assert [a["id"] for a in agents] == [str(enabled)]
    assert agents[0]["cardUrl"].endswith(f"/api/v1/a2a/{enabled}/.well-known/agent-card.json")


# --- JSON-RPC message/send + tasks/get -------------------------------------

_ECHO_FLOW = Path(__file__).parents[3] / "data" / "chat_echo_no_llm.json"


@pytest.fixture
def echo_flow_data():
    """ChatInput -> ChatOutput echo flow (no LLM); a sync run returns input_value verbatim."""
    return orjson.loads(_ECHO_FLOW.read_bytes())["data"]


def _text_message(text, message_id="m1", context_id=None, task_id=None):
    message = {"role": "user", "parts": [{"kind": "text", "text": text}], "messageId": message_id}
    if context_id is not None:
        message["contextId"] = context_id
    if task_id is not None:
        message["taskId"] = task_id
    return {"message": message}


async def _jsonrpc(client: AsyncClient, flow_id, method, params, rpc_id=1, headers=None):
    return await client.post(
        f"api/v1/a2a/{flow_id}/jsonrpc",
        json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
        headers=headers,
    )


async def _create_api_key(user_id):
    """Create a real langflow API key for a user; returns the raw (unmasked) key."""
    from langflow.services.database.models.api_key.crud import create_api_key
    from langflow.services.database.models.api_key.model import ApiKeyCreate

    async with session_scope() as session:
        unmasked = await create_api_key(session, ApiKeyCreate(name=f"a2a-key-{uuid.uuid4().hex[:8]}"), user_id)
        await session.commit()
        return unmasked.api_key


async def _create_other_user():
    """Create a distinct second user.

    active_user / active_super_user share a username, so they resolve to the same row
    and can't serve as separate owners.
    """
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User

    async with session_scope() as session:
        user = User(
            username=f"a2a-other-{uuid.uuid4().hex[:8]}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


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
async def test_message_stream_yields_lifecycle_sse(client: AsyncClient, active_user, echo_flow_data):
    """message/stream streams the run as SSE: a working status, the echoed artifact, then a final completed status."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)

    async with client.stream(
        "POST",
        f"api/v1/a2a/{flow_id}/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": _text_message("hello a2a")},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [
            orjson.loads(line[len("data:") :])["result"]
            async for line in resp.aiter_lines()
            if line.startswith("data:")
        ]

    assert any(e["kind"] == "status-update" and e["status"]["state"] == "working" for e in events)
    artifacts = [e for e in events if e["kind"] == "artifact-update"]
    assert artifacts[0]["artifact"]["parts"][0]["text"] == "hello a2a"
    assert events[-1]["kind"] == "status-update"
    assert events[-1]["status"]["state"] == "completed"
    assert events[-1]["final"] is True


@pytest.mark.usefixtures("a2a_flag_on")
async def test_resubscribe_to_terminal_task_errors_without_hanging(client: AsyncClient, active_user, echo_flow_data):
    """tasks/resubscribe to an already-finished task ends with an error frame, not a hang.

    The sync run is terminal by the time a client could re-attach, so the SDK returns a
    spec error (terminal/no-live-queue) rather than streaming. The test completing at all
    is the no-hang proof.
    """
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    sent = (await _jsonrpc(client, flow_id, "message/send", _text_message("done"))).json()["result"]
    task_id = sent["id"]

    async with client.stream(
        "POST",
        f"api/v1/a2a/{flow_id}/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": task_id}},
    ) as resp:
        assert resp.status_code == 200
        frames = [orjson.loads(line[len("data:") :]) async for line in resp.aiter_lines() if line.startswith("data:")]

    assert any("error" in f for f in frames)
    assert not any(f.get("result", {}).get("kind") == "artifact-update" for f in frames)


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


# --- multi-turn / contextId ------------------------------------------------


async def _session_texts(session_id) -> set[str]:
    """The stored message texts under a chat session_id."""
    from langflow.services.database.models import MessageTable
    from sqlmodel import select

    async with session_scope() as session:
        rows = (await session.exec(select(MessageTable).where(MessageTable.session_id == session_id))).all()
    return {row.text for row in rows}


def _derive_session(owner_id, flow_id, context_id) -> str | None:
    """The internal chat session_id the A2A run derives from a client contextId.

    Mirrors ``_run_flow`` exactly: the contextId is namespaced under a per-(owner, flow)
    virtual id, and an over-bound composed key is hashed (never collapsed to the shared
    per-flow default), so stored messages never sit under the bare, client-controlled
    contextId.
    """
    import hashlib

    from langflow.api.utils.flow_utils import compute_virtual_flow_id, scope_session_to_namespace
    from lfx.schema.workflow import GLOBAL_KEY_MAX_LEN

    if not context_id:
        return None
    namespace = str(compute_virtual_flow_id(owner_id, flow_id))
    scoped = scope_session_to_namespace(context_id, namespace)
    if scoped and len(scoped) <= GLOBAL_KEY_MAX_LEN:
        return scoped
    return f"{namespace}:{hashlib.sha256(context_id.encode()).hexdigest()}"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_context_id_threads_into_flow_session(client: AsyncClient, active_user, echo_flow_data):
    """The A2A contextId threads into the flow session, so one conversation maps to one chat session.

    The echo flow's ChatInput/ChatOutput persist messages under the run's session_id. After a
    message/send carrying a contextId, the stored messages sit under the namespaced session
    derived from that contextId, proving it threaded through to the v2 run rather than the default
    str(flow.id) fallback. Nothing lands under the bare, client-controlled contextId. The returned
    Task still echoes the original contextId.
    """
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    context_id = f"conv-{uuid.uuid4().hex}"

    resp = await _jsonrpc(client, flow_id, "message/send", _text_message("hello a2a", context_id=context_id))
    result = resp.json()["result"]

    assert result["contextId"] == context_id

    # The run persists its output under the namespaced session, not the bare contextId
    # (and not the default str(flow.id) fallback).
    scoped_texts = await _session_texts(_derive_session(active_user.id, flow_id, context_id))
    assert "hello a2a" in scoped_texts, "the run's messages were not stored under the namespaced session"
    assert await _session_texts(context_id) == set(), "messages must not be addressable by the bare client contextId"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_distinct_context_ids_get_distinct_sessions(client: AsyncClient, active_user, echo_flow_data):
    """Two different contextIds land in two different sessions (conversations stay isolated)."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    ctx_a = f"conv-{uuid.uuid4().hex}"
    ctx_b = f"conv-{uuid.uuid4().hex}"

    await _jsonrpc(client, flow_id, "message/send", _text_message("from a", context_id=ctx_a))
    await _jsonrpc(client, flow_id, "message/send", _text_message("from b", context_id=ctx_b))

    a_texts = await _session_texts(_derive_session(active_user.id, flow_id, ctx_a))
    b_texts = await _session_texts(_derive_session(active_user.id, flow_id, ctx_b))

    assert "from a" in a_texts
    assert "from b" in b_texts
    assert "from b" not in a_texts


@pytest.mark.usefixtures("a2a_flag_on")
async def test_same_context_id_across_flows_does_not_share_session(client: AsyncClient, active_user, echo_flow_data):
    """The same contextId on two different flows does NOT share chat memory (cross-flow hijack fix).

    The contextId is namespaced under a per-(owner, flow) virtual id, so an identical client
    contextId resolves to a different session per flow. Multi-turn on the same flow with the same
    contextId still shares one session.
    """
    flow_a = await _create_flow(active_user.id, data=echo_flow_data)
    flow_b = await _create_flow(active_user.id, data=echo_flow_data)
    shared_ctx = f"conv-{uuid.uuid4().hex}"  # same client-supplied contextId on both flows

    # Two turns on flow_a (same contextId) prove same-flow memory sharing.
    await _jsonrpc(client, flow_a, "message/send", _text_message("a turn 1", context_id=shared_ctx))
    await _jsonrpc(client, flow_a, "message/send", _text_message("a turn 2", context_id=shared_ctx))
    # One turn on flow_b reusing the same contextId must not bleed into flow_a's session.
    await _jsonrpc(client, flow_b, "message/send", _text_message("b turn 1", context_id=shared_ctx))

    session_a = _derive_session(active_user.id, flow_a, shared_ctx)
    session_b = _derive_session(active_user.id, flow_b, shared_ctx)
    assert session_a != session_b

    a_texts = await _session_texts(session_a)
    b_texts = await _session_texts(session_b)

    # Same flow + same contextId shares memory across turns.
    assert {"a turn 1", "a turn 2"} <= a_texts
    # Cross-flow isolation: flow_b's reuse of the contextId stays out of flow_a's session.
    assert "b turn 1" in b_texts
    assert "b turn 1" not in a_texts
    assert not (a_texts & b_texts)
    # And nothing is addressable by the bare, shared contextId.
    assert await _session_texts(shared_ctx) == set()


@pytest.mark.usefixtures("a2a_flag_on")
async def test_oversized_context_ids_get_distinct_hashed_sessions(client: AsyncClient, active_user, echo_flow_data):
    """An over-bound contextId is hashed per-conversation, NOT collapsed to the shared default.

    contextId is client-controlled on a public endpoint, so a value whose namespaced key would
    exceed the btree-capped session_id column is hashed (still flow-scoped). The run succeeds and
    the Task echoes the raw contextId, but two different long contextIds land in two DIFFERENT
    sessions, and neither lands in the shared str(flow.id) default (which would re-open the
    cross-caller leak) nor under the bare contextId.
    """
    from lfx.schema.workflow import GLOBAL_KEY_MAX_LEN

    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    huge_a = "a" * (GLOBAL_KEY_MAX_LEN + 64)
    huge_b = "b" * (GLOBAL_KEY_MAX_LEN + 64)

    result_a = (await _jsonrpc(client, flow_id, "message/send", _text_message("long a", context_id=huge_a))).json()
    await _jsonrpc(client, flow_id, "message/send", _text_message("long b", context_id=huge_b))

    assert result_a["result"]["status"]["state"] == "completed"
    assert result_a["result"]["contextId"] == huge_a  # protocol value preserved, just not used verbatim as session_id

    session_a = _derive_session(active_user.id, flow_id, huge_a)
    session_b = _derive_session(active_user.id, flow_id, huge_b)

    # Two different long contextIds get two different (bounded, hashed) sessions.
    assert session_a != session_b
    assert len(session_a) <= GLOBAL_KEY_MAX_LEN
    assert "long a" in await _session_texts(session_a)
    assert "long b" in await _session_texts(session_b)
    # Never the shared per-flow default, and never the unbounded bare contextId.
    assert await _session_texts(str(flow_id)) == set()
    assert await _session_texts(huge_a) == set()
    assert "long b" not in await _session_texts(session_a)


# --- input-required (HITL) -------------------------------------------------

_HUMAN_INPUT_FLOW = Path(__file__).parents[3] / "data" / "human_input_flow.json"


@pytest.fixture
def human_input_flow_data():
    """HumanInput -> ChatOutput flow: pauses for an Approve/Reject decision, then routes on it."""
    return orjson.loads(_HUMAN_INPUT_FLOW.read_bytes())["data"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_pausing_flow_returns_input_required(client: AsyncClient, active_user, human_input_flow_data):
    """A flow that pauses for human input returns an input-required Task carrying the prompt."""
    flow_id = await _create_flow(active_user.id, data=human_input_flow_data)

    result = (await _jsonrpc(client, flow_id, "message/send", _text_message("start"))).json()["result"]

    assert result["kind"] == "task"
    assert result["status"]["state"] == "input-required"
    assert result["status"]["message"]["parts"][0]["text"] == "Approve this?"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_resume_input_required_task_completes(client: AsyncClient, active_user, human_input_flow_data):
    """A follow-up message on the input-required task supplies the decision and completes the run.

    The second message/send references the same taskId + contextId; "Approve" maps to the
    HumanInput's approve branch, so the run resumes from the checkpoint and the chosen branch's
    ChatOutput produces the answer.
    """
    flow_id = await _create_flow(active_user.id, data=human_input_flow_data)

    paused = (await _jsonrpc(client, flow_id, "message/send", _text_message("start"))).json()["result"]
    assert paused["status"]["state"] == "input-required"
    task_id, context_id = paused["id"], paused["contextId"]

    resumed = (
        await _jsonrpc(
            client,
            flow_id,
            "message/send",
            _text_message("Approve", message_id="m2", context_id=context_id, task_id=task_id),
        )
    ).json()["result"]

    assert resumed["id"] == task_id
    assert resumed["status"]["state"] == "completed"
    assert resumed["artifacts"][0]["parts"][0]["text"] == "Approve this?"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_unmatched_decision_re_parks_task(client: AsyncClient, active_user, human_input_flow_data):
    """A reply that matches no offered action re-parks the task instead of burning it.

    The run isn't advanced and the checkpoint is kept, so a later valid reply still completes it.
    """
    flow_id = await _create_flow(active_user.id, data=human_input_flow_data)
    paused = (await _jsonrpc(client, flow_id, "message/send", _text_message("start"))).json()["result"]
    task_id, context_id = paused["id"], paused["contextId"]

    # "maybe" is neither an allowed action nor an option label.
    reparked = (
        await _jsonrpc(
            client,
            flow_id,
            "message/send",
            _text_message("maybe", message_id="m2", context_id=context_id, task_id=task_id),
        )
    ).json()["result"]
    assert reparked["status"]["state"] == "input-required"
    assert reparked["status"]["message"]["parts"][0]["text"] == "Approve this?"

    # The task survived: a valid reply still completes it.
    done = (
        await _jsonrpc(
            client,
            flow_id,
            "message/send",
            _text_message("Approve", message_id="m3", context_id=context_id, task_id=task_id),
        )
    ).json()["result"]
    assert done["status"]["state"] == "completed"
    assert done["artifacts"][0]["parts"][0]["text"] == "Approve this?"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_resume_via_other_flow_is_rejected(client: AsyncClient, active_user, human_input_flow_data):
    """A task parked under one flow cannot be resumed through a different flow's endpoint."""
    flow_a = await _create_flow(active_user.id, data=human_input_flow_data)
    flow_b = await _create_flow(active_user.id, data=human_input_flow_data)

    paused = (await _jsonrpc(client, flow_a, "message/send", _text_message("start"))).json()["result"]
    task_id, context_id = paused["id"], paused["contextId"]

    # Same task id, but sent to flow B: must not run flow A's graph.
    via_b = (
        await _jsonrpc(
            client,
            flow_b,
            "message/send",
            _text_message("Approve", message_id="m2", context_id=context_id, task_id=task_id),
        )
    ).json()["result"]

    assert via_b["status"]["state"] == "failed"


# --- apikey auth enforcement ----------------------------------------------


async def _apikey_flow(active_user, echo_flow_data):
    """An agent flow inside an apikey-auth folder."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "apikey"})
    return await _create_flow(active_user.id, data=echo_flow_data, folder_id=folder_id)


@pytest.mark.usefixtures("a2a_flag_on")
async def test_apikey_folder_rejects_missing_key(client: AsyncClient, active_user, echo_flow_data):
    """An apikey-folder flow 401s without an x-api-key."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)

    assert (await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))).status_code == 401


@pytest.mark.usefixtures("a2a_flag_on")
async def test_apikey_folder_rejects_invalid_key(client: AsyncClient, active_user, echo_flow_data):
    """An apikey-folder flow 401s with a bogus key."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)

    resp = await _jsonrpc(client, flow_id, "message/send", _text_message("hi"), headers={"x-api-key": "bogus"})

    assert resp.status_code == 401


@pytest.mark.usefixtures("a2a_flag_on")
async def test_apikey_folder_accepts_owner_key(client: AsyncClient, active_user, echo_flow_data):
    """A valid key owned by the flow owner runs the flow."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)
    key = await _create_api_key(active_user.id)

    resp = await _jsonrpc(client, flow_id, "message/send", _text_message("hello a2a"), headers={"x-api-key": key})

    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"]["state"] == "completed"
    assert result["artifacts"][0]["parts"][0]["text"] == "hello a2a"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_apikey_folder_rejects_other_user_key(client: AsyncClient, active_user, echo_flow_data):
    """A valid key owned by a different user 401s (owner-scoped; no privilege escalation)."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)
    other_user_id = await _create_other_user()
    other_key = await _create_api_key(other_user_id)

    resp = await _jsonrpc(client, flow_id, "message/send", _text_message("hi"), headers={"x-api-key": other_key})

    assert resp.status_code == 401


@pytest.mark.usefixtures("a2a_flag_on")
async def test_none_folder_stays_public(client: AsyncClient, active_user, echo_flow_data):
    """A none-auth folder needs no key (the public A2A agent model)."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "none"})
    flow_id = await _create_flow(active_user.id, data=echo_flow_data, folder_id=folder_id)

    resp = await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))

    assert resp.status_code == 200
    assert resp.json()["result"]["status"]["state"] == "completed"


@pytest.mark.usefixtures("a2a_flag_on")
async def test_oauth_folder_fails_closed(client: AsyncClient, active_user, echo_flow_data):
    """A2A can't enforce oauth yet, so an oauth folder fails closed (403), never public.

    Otherwise a protected flow would run anonymously as its owner.
    """
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "oauth"})
    flow_id = await _create_flow(active_user.id, data=echo_flow_data, folder_id=folder_id)

    assert (await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))).status_code == 403


@pytest.mark.usefixtures("a2a_flag_on")
async def test_unknown_folder_auth_type_fails_closed(client: AsyncClient, active_user, echo_flow_data):
    """Any protected auth type A2A doesn't understand fails closed (403), never public."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "saml"})
    flow_id = await _create_flow(active_user.id, data=echo_flow_data, folder_id=folder_id)

    assert (await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))).status_code == 403


@pytest.mark.usefixtures("a2a_flag_on")
async def test_card_get_public_for_apikey_folder(client: AsyncClient, active_user, echo_flow_data):
    """Discovery stays public even for an apikey folder (only the jsonrpc route enforces)."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)

    assert (await client.get(_card_url(flow_id))).status_code == 200


@pytest.mark.usefixtures("a2a_flag_on")
async def test_stream_rejects_missing_key_plain_401(client: AsyncClient, active_user, echo_flow_data):
    """message/stream 401s before the SSE body opens (a plain 401, not an SSE error frame)."""
    flow_id = await _apikey_flow(active_user, echo_flow_data)

    async with client.stream(
        "POST",
        f"api/v1/a2a/{flow_id}/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": _text_message("hi")},
    ) as resp:
        assert resp.status_code == 401
        assert not resp.headers["content-type"].startswith("text/event-stream")


# --- push notifications ----------------------------------------------------


@pytest.mark.usefixtures("a2a_flag_on")
async def test_card_advertises_push_notifications(client: AsyncClient, active_user, flow_data):
    """The card advertises push notifications, matching the handler capability that gates the methods."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["capabilities"]["pushNotifications"] is True


@pytest.mark.usefixtures("client")
async def test_validate_webhook_url_blocks_internal_targets():
    """The SSRF guard rejects private/loopback/link-local/non-http webhook targets, allows public ones."""
    from langflow.api.v1.a2a_utils import validate_webhook_url

    for bad in (
        "http://127.0.0.1/h",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata
        "http://10.0.0.1/h",
        "http://[::1]/h",
        "ftp://8.8.8.8/h",
        "https:///nohost",
    ):
        with pytest.raises(ValueError, match="webhook"):
            await validate_webhook_url(bad)

    # Public IP literal: resolves without DNS, passes.
    await validate_webhook_url("https://8.8.8.8/hook")


@pytest.mark.usefixtures("client")
async def test_validate_webhook_url_floor_holds_with_global_ssrf_off(monkeypatch):
    """A2A webhook safety must not depend on the global SSRF toggle.

    LANGFLOW_SSRF_PROTECTION_ENABLED is an API-Request-component setting ops can disable;
    validate_and_resolve_url returns [] with no enforcement when it's off. The A2A guard
    keeps a hard IP floor regardless, so a webhook resolving to a private/metadata IP is
    still rejected, while a public host still validates and returns IPs for DNS pinning.
    """
    from langflow.api.v1.a2a_utils import validate_webhook_url

    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")

    for bad in ("http://169.254.169.254/latest/meta-data", "http://127.0.0.1/h", "http://10.0.0.1/h"):
        with pytest.raises(ValueError, match="webhook"):
            await validate_webhook_url(bad)

    # Public IP still passes the floor and is returned for DNS pinning even with the toggle off.
    assert await validate_webhook_url("https://8.8.8.8/hook") == ["8.8.8.8"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_push_config_internal_url_rejected(client: AsyncClient, active_user, echo_flow_data):
    """Registering a webhook that targets an internal address is rejected by the SSRF guard."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    sent = (await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))).json()["result"]
    task_id = sent["id"]

    params = {"taskId": task_id, "pushNotificationConfig": {"url": "http://169.254.169.254/hook"}}
    body = (await _jsonrpc(client, flow_id, "tasks/pushNotificationConfig/set", params)).json()

    assert "error" in body


@pytest.mark.usefixtures("a2a_flag_on")
async def test_push_config_public_url_accepted(client: AsyncClient, active_user, echo_flow_data):
    """A public webhook URL registers cleanly (the guard only blocks internal targets)."""
    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    sent = (await _jsonrpc(client, flow_id, "message/send", _text_message("hi"))).json()["result"]
    task_id = sent["id"]

    params = {"taskId": task_id, "pushNotificationConfig": {"url": "https://8.8.8.8/hook"}}
    body = (await _jsonrpc(client, flow_id, "tasks/pushNotificationConfig/set", params)).json()

    assert "error" not in body
    assert "result" in body


# --- client component (consume a remote A2A agent) -------------------------


@pytest.mark.usefixtures("a2a_flag_on")
async def test_a2a_agent_component_calls_remote_agent(client: AsyncClient, active_user, echo_flow_data):
    """The A2A Agent component sends a message to a remote agent and returns its reply.

    Drives the real a2a-sdk client against this app's own A2A server (an echo agent flow),
    so the full card-resolve + message/send round-trip runs in-process, no mocks.
    """
    from lfx.components.models_and_agents.a2a_agent import call_a2a_agent

    flow_id = await _create_flow(active_user.id, data=echo_flow_data)
    agent_url = f"{str(client.base_url).rstrip('/')}/api/v1/a2a/{flow_id}"

    answer = await call_a2a_agent(agent_url, "hello a2a", httpx_client=client)

    assert answer == "hello a2a"


@pytest.mark.usefixtures("client")
async def test_push_dispatch_rejects_rebound_private_ip():
    """Dispatch re-validates the webhook, so a config now pointing at a private/metadata IP is dropped.

    Registration validation can't stop a host that re-resolves to an internal IP after it
    was registered (DNS rebinding). Calling the live sender's dispatch path directly with a
    config whose URL targets the cloud metadata IP (bypassing registration, as a rebind
    would) must return False (not sent) rather than POST to the internal address.
    """
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1.a2a import _PUSH_SENDER

    push_info = pb.TaskPushNotificationConfig(url="http://169.254.169.254/hook")

    # event is irrelevant: the SSRF check fires before any payload is built or sent.
    sent = await _PUSH_SENDER._dispatch_notification(None, push_info, "task-rebind")

    assert sent is False


def test_webhook_pin_host_matches_httpx_connect_host_for_idn():
    """The DNS-pin key must be the host httpx actually connects to, not the unicode hostname.

    httpx/httpcore connect using the IDNA/punycode ``raw_host``; ``urlparse().hostname`` keeps
    the unicode form. Pinning by the unicode host means the pin key never matches the connected
    host for an internationalized webhook, so the pin is silently bypassed (TOCTOU rebind). The
    pin host and the connect host must be the identical punycode string.
    """
    from urllib.parse import urlparse

    import httpx
    from langflow.api.v1.a2a_utils import webhook_pin_host

    url = "http://exämple.com/hook"
    pin = webhook_pin_host(url)

    # Pin == exactly what httpcore connects to (raw_host, IDNA-encoded), and NOT the old key.
    assert pin == httpx.URL(url).raw_host.decode("ascii") == "xn--exmple-cua.com"
    assert pin != urlparse(url).hostname  # the unicode host that would have bypassed the pin


@pytest.mark.usefixtures("a2a_flag_on")
async def test_push_config_is_flow_scoped(client: AsyncClient, active_user, echo_flow_data):
    """A push config registered under flow A is invisible to flow B, even with the same task id.

    The store is scoped by flow (not by task id alone), so flow B can't read flow A's webhook.
    """
    flow_a = await _create_flow(active_user.id, data=echo_flow_data)
    flow_b = await _create_flow(active_user.id, data=echo_flow_data)

    sent = (await _jsonrpc(client, flow_a, "message/send", _text_message("hi"))).json()["result"]
    task_id = sent["id"]

    webhook = f"https://8.8.8.8/hook-{uuid.uuid4().hex}"
    set_params = {"taskId": task_id, "pushNotificationConfig": {"url": webhook}}
    assert "result" in (await _jsonrpc(client, flow_a, "tasks/pushNotificationConfig/set", set_params)).json()

    # Flow A (the registering flow) sees its own webhook back.
    list_a = await _jsonrpc(client, flow_a, "tasks/pushNotificationConfig/list", {"id": task_id})
    assert webhook in list_a.text

    # Flow B, asking for the same task id, does not see flow A's webhook.
    list_b = await _jsonrpc(client, flow_b, "tasks/pushNotificationConfig/list", {"id": task_id})
    assert webhook not in list_b.text


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
