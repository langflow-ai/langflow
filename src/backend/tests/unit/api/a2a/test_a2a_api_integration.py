"""Black-box HTTP integration test for the A2A protocol surface.

This test treats Langflow's A2A endpoints like an external A2A client would:
every interaction goes through the FastAPI ``client`` fixture over HTTP. It does
NOT import A2A internals (task manager, router helpers, the in-process A2A
client) and it does NOT mock flow execution — a real, no-API-key Langflow flow
(``MemoryChatbotNoLLM``) is exposed as an A2A agent and exercised end to end.

Protocol shapes are validated against the official ``a2a-sdk`` pydantic types
(``AgentCard``, ``Task``), so the bytes on the wire are spec-shaped, not just
internally consistent.

Coverage:
- Discovery: public AgentCard (no auth) + extended card (auth-gated)
- 404 paths: unknown slug, a2a-disabled flow, instance kill switch
- Config admin: PUT/GET a2a-config, auth, invalid slug (422), duplicate (409)
- message:send with real execution (completed task, artifacts, probe echo)
- Task polling, listing by contextId, cancellation
- Multi-turn with a shared contextId
- message:stream real execution (working + completed SSE, output surfaces)
- Auth enforcement on protected endpoints
- Idempotent retry (cached task on re-sent taskId)
"""

import json
from pathlib import Path

import pytest
from a2a.types import AgentCard, Task
from httpx import AsyncClient
from langflow.services.database.models.flow.model import FlowCreate

pytestmark = pytest.mark.asyncio

# Real, runnable, no-API-key flow shipped with the test suite. It has no LLM and
# emits a prompt that echoes the user input as "User: <input>".
_FLOW_PATH = Path(__file__).resolve().parents[3] / "data" / "MemoryChatbotNoLLM.json"

_BAD_AUTH = {"Authorization": "Bearer invalid-token"}


# ---------------------------------------------------------------------------
# Helpers — all black-box HTTP, no A2A internals.
# ---------------------------------------------------------------------------


def _load_flow_data() -> dict:
    raw = json.loads(_FLOW_PATH.read_text(encoding="utf-8"))
    return raw.get("data", raw)


async def _create_flow(client: AsyncClient, headers: dict, *, name: str) -> str:
    """Create the no-LLM flow via the public flows API. Returns flow_id."""
    flow = FlowCreate(name=name, description="No-LLM flow exposed via A2A", data=_load_flow_data())
    create = await client.post("api/v1/flows/", json=flow.model_dump(), headers=headers)
    assert create.status_code == 201, create.text
    return create.json()["id"]


async def _set_a2a_config(client: AsyncClient, headers: dict, flow_id: str, body: dict):
    return await client.put(f"api/v1/flows/{flow_id}/a2a-config", json=body, headers=headers)


async def _expose_flow_as_a2a(client: AsyncClient, headers: dict, *, slug: str, name: str) -> str:
    """Create the flow and enable A2A on it. Returns flow_id."""
    flow_id = await _create_flow(client, headers, name=name)
    cfg = await _set_a2a_config(
        client, headers, flow_id, {"a2a_enabled": True, "a2a_agent_slug": slug, "a2a_name": name}
    )
    assert cfg.status_code == 200, cfg.text
    return flow_id


def _message_body(text: str, *, context_id: str | None = None, task_id: str | None = None) -> dict:
    msg: dict = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": "msg-blackbox",
        }
    }
    if context_id is not None:
        msg["message"]["contextId"] = context_id
    if task_id is not None:
        msg["taskId"] = task_id
    return msg


def _artifact_text(task: dict) -> str:
    """Concatenate all text parts across a Task's artifacts."""
    chunks = [
        part["text"]
        for artifact in task.get("artifacts") or []
        for part in artifact.get("parts") or []
        if part.get("kind") == "text" and part.get("text")
    ]
    return " ".join(chunks)


def _parse_sse_events(raw_text: str) -> list[dict]:
    """Parse SSE ``data:`` lines into JSON event dicts."""
    events = []
    for raw_line in raw_text.strip().split("\n"):
        line = raw_line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return events


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestA2ADiscoveryHTTP:
    """Public + extended AgentCard discovery over HTTP."""

    async def test_public_agent_card_no_auth_validates(self, client: AsyncClient, logged_in_headers):
        """The well-known AgentCard is public (no auth) and spec-shaped."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="disc-pub", name="Discovery Agent")

        # No auth header at all — public discovery endpoint.
        resp = await client.get("/a2a/disc-pub/.well-known/agent-card.json", headers=_BAD_AUTH)
        assert resp.status_code == 200, resp.text

        card = resp.json()
        AgentCard.model_validate(card)
        assert card["name"] == "Discovery Agent"
        assert card["capabilities"]["streaming"] is True

    async def test_extended_card_requires_auth(self, client: AsyncClient, logged_in_headers):
        """The extended card is auth-gated: 401/403 without auth, 200 with it."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="disc-ext", name="Extended Agent")

        unauth = await client.get("/a2a/disc-ext/v1/card", headers=_BAD_AUTH)
        assert unauth.status_code in (401, 403)

        authed = await client.get("/a2a/disc-ext/v1/card", headers=logged_in_headers)
        assert authed.status_code == 200, authed.text
        card = authed.json()
        AgentCard.model_validate(card)
        assert card.get("extended") is True


# ---------------------------------------------------------------------------
# 404 / not-found paths
# ---------------------------------------------------------------------------


class TestA2ANotFoundHTTP:
    """Unknown slug, disabled flow, and the instance kill switch all 404."""

    async def test_unknown_slug_returns_404(self, client: AsyncClient):
        resp = await client.get("/a2a/no-such-agent/.well-known/agent-card.json")
        assert resp.status_code == 404

    async def test_a2a_disabled_flow_returns_404(self, client: AsyncClient, logged_in_headers):
        """A flow that exists but never enabled A2A is not discoverable."""
        await _create_flow(client, logged_in_headers, name="Never Exposed")
        resp = await client.get("/a2a/never-exposed/.well-known/agent-card.json")
        assert resp.status_code == 404

    async def test_instance_kill_switch_hides_enabled_agent(
        self, client: AsyncClient, logged_in_headers, monkeypatch
    ):
        """LANGFLOW_A2A_ENABLED=false 404s even an enabled agent; restored after."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="kill-switch", name="Killable Agent")

        # Sanity: visible while enabled.
        before = await client.get("/a2a/kill-switch/.well-known/agent-card.json")
        assert before.status_code == 200

        monkeypatch.setenv("LANGFLOW_A2A_ENABLED", "false")
        killed = await client.get("/a2a/kill-switch/.well-known/agent-card.json")
        assert killed.status_code == 404

        # monkeypatch restores the env var at teardown; verify within the test.
        monkeypatch.undo()
        restored = await client.get("/a2a/kill-switch/.well-known/agent-card.json")
        assert restored.status_code == 200

    async def test_instance_kill_switch_blocks_action_routes(
        self, client: AsyncClient, logged_in_headers, monkeypatch
    ):
        """The kill switch 404s the action routes too (send/stream/tasks/cancel),
        not just discovery — it is the documented instance-wide rollback."""
        slug = "kill-actions"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Killable Actions")

        # Create a real task while enabled so we have an id to probe.
        sent = await client.post(
            f"/a2a/{slug}/v1/message:send",
            json=_message_body("hi", context_id="ctx-kill"),
            headers=logged_in_headers,
        )
        assert sent.status_code == 200
        task_id = sent.json()["id"]

        monkeypatch.setenv("LANGFLOW_A2A_ENABLED", "false")
        try:
            send = await client.post(
                f"/a2a/{slug}/v1/message:send", json=_message_body("again"), headers=logged_in_headers
            )
            assert send.status_code == 404
            stream = await client.post(
                f"/a2a/{slug}/v1/message:stream", json=_message_body("x"), headers=logged_in_headers
            )
            assert stream.status_code == 404
            assert (await client.get(f"/a2a/{slug}/v1/tasks/{task_id}", headers=logged_in_headers)).status_code == 404
            assert (await client.get(f"/a2a/{slug}/v1/tasks", headers=logged_in_headers)).status_code == 404
            cancel = await client.post(f"/a2a/{slug}/v1/tasks/{task_id}:cancel", headers=logged_in_headers)
            assert cancel.status_code == 404
        finally:
            monkeypatch.undo()


# ---------------------------------------------------------------------------
# Config admin
# ---------------------------------------------------------------------------


class TestA2AConfigAdminHTTP:
    """PUT/GET /api/v1/flows/{id}/a2a-config: auth, validation, uniqueness."""

    async def test_config_requires_auth(self, client: AsyncClient, logged_in_headers):
        flow_id = await _create_flow(client, logged_in_headers, name="Config Auth Flow")

        put = await _set_a2a_config(client, _BAD_AUTH, flow_id, {"a2a_enabled": True, "a2a_agent_slug": "cfg-auth"})
        assert put.status_code in (401, 403)

        get = await client.get(f"api/v1/flows/{flow_id}/a2a-config", headers=_BAD_AUTH)
        assert get.status_code in (401, 403)

    async def test_get_config_round_trips(self, client: AsyncClient, logged_in_headers):
        flow_id = await _expose_flow_as_a2a(client, logged_in_headers, slug="cfg-rt", name="Config RT")
        get = await client.get(f"api/v1/flows/{flow_id}/a2a-config", headers=logged_in_headers)
        assert get.status_code == 200, get.text
        cfg = get.json()
        assert cfg["a2a_enabled"] is True
        assert cfg["a2a_agent_slug"] == "cfg-rt"
        assert cfg["a2a_name"] == "Config RT"

    async def test_invalid_slug_returns_422(self, client: AsyncClient, logged_in_headers):
        flow_id = await _create_flow(client, logged_in_headers, name="Bad Slug Flow")
        resp = await _set_a2a_config(
            client, logged_in_headers, flow_id, {"a2a_enabled": True, "a2a_agent_slug": "INVALID SLUG!"}
        )
        assert resp.status_code == 422, resp.text

    async def test_duplicate_slug_returns_409(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="dup-slug", name="First")
        second_id = await _create_flow(client, logged_in_headers, name="Second")
        resp = await _set_a2a_config(
            client, logged_in_headers, second_id, {"a2a_enabled": True, "a2a_agent_slug": "dup-slug"}
        )
        assert resp.status_code == 409, resp.text


# ---------------------------------------------------------------------------
# message:send — real execution
# ---------------------------------------------------------------------------


class TestA2AMessageSendHTTP:
    """message:send drives real flow execution to a completed Task."""

    async def test_send_real_execution_completes(self, client: AsyncClient, logged_in_headers):
        """Probe text must reappear in the artifact, proving real execution."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="send-real", name="Send Agent")

        probe = "PingProbe-42"
        resp = await client.post(
            "/a2a/send-real/v1/message:send",
            json=_message_body(probe, context_id="ctx-send-real"),
            headers=logged_in_headers,
        )
        assert resp.status_code == 200, resp.text
        task = resp.json()

        assert task["status"]["state"] == "completed", task
        Task.model_validate(task)
        assert task["contextId"] == "ctx-send-real"

        text = _artifact_text(task)
        assert text, f"expected text artifacts, got: {task}"
        assert probe in text, f"flow output did not reflect input: {text!r}"

    async def test_send_requires_auth(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="send-auth", name="Send Auth")
        resp = await client.post(
            "/a2a/send-auth/v1/message:send", json=_message_body("hello"), headers=_BAD_AUTH
        )
        assert resp.status_code in (401, 403)

    async def test_send_unknown_slug_returns_404(self, client: AsyncClient, logged_in_headers):
        resp = await client.post(
            "/a2a/no-such-send/v1/message:send", json=_message_body("hello"), headers=logged_in_headers
        )
        assert resp.status_code == 404

    async def test_idempotent_retry_returns_cached_task(self, client: AsyncClient, logged_in_headers):
        """Re-sending the same taskId after completion returns the cached task."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="send-retry", name="Retry Agent")

        body = _message_body("RetryProbe-1", context_id="ctx-retry", task_id="task-idem-1")
        first = await client.post("/a2a/send-retry/v1/message:send", json=body, headers=logged_in_headers)
        assert first.status_code == 200, first.text
        first_task = first.json()
        assert first_task["id"] == "task-idem-1"
        assert first_task["status"]["state"] == "completed"

        second = await client.post("/a2a/send-retry/v1/message:send", json=body, headers=logged_in_headers)
        assert second.status_code == 200, second.text
        second_task = second.json()
        assert second_task["id"] == first_task["id"]
        assert second_task["status"]["state"] == "completed"


# ---------------------------------------------------------------------------
# Task endpoints — polling, listing, cancellation
# ---------------------------------------------------------------------------


class TestA2ATaskEndpointsHTTP:
    """get/list/cancel task endpoints over HTTP."""

    async def test_poll_list_and_cancel(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="task-ops", name="Task Ops Agent")

        send = await client.post(
            "/a2a/task-ops/v1/message:send",
            json=_message_body("TaskOpsProbe", context_id="ctx-task-ops"),
            headers=logged_in_headers,
        )
        assert send.status_code == 200, send.text
        task_id = send.json()["id"]

        # Poll.
        polled = await client.get(f"/a2a/task-ops/v1/tasks/{task_id}", headers=logged_in_headers)
        assert polled.status_code == 200, polled.text
        assert polled.json()["id"] == task_id
        assert polled.json()["status"]["state"] == "completed"

        # List by contextId.
        listed = await client.get("/a2a/task-ops/v1/tasks?contextId=ctx-task-ops", headers=logged_in_headers)
        assert listed.status_code == 200, listed.text
        ids = {t["id"] for t in listed.json()}
        assert task_id in ids

        # Cancel.
        cancel = await client.post(f"/a2a/task-ops/v1/tasks/{task_id}:cancel", headers=logged_in_headers)
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["status"]["state"] == "canceled"

    async def test_task_endpoints_require_auth(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="task-auth", name="Task Auth Agent")
        send = await client.post(
            "/a2a/task-auth/v1/message:send",
            json=_message_body("AuthTaskProbe"),
            headers=logged_in_headers,
        )
        task_id = send.json()["id"]

        get = await client.get(f"/a2a/task-auth/v1/tasks/{task_id}", headers=_BAD_AUTH)
        assert get.status_code in (401, 403)

        lst = await client.get("/a2a/task-auth/v1/tasks", headers=_BAD_AUTH)
        assert lst.status_code in (401, 403)

    async def test_nonexistent_task_returns_404(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="task-missing", name="Missing Task Agent")
        resp = await client.get("/a2a/task-missing/v1/tasks/does-not-exist", headers=logged_in_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multi-turn
# ---------------------------------------------------------------------------


class TestA2AMultiTurnHTTP:
    """Two message:send calls on a shared contextId both complete."""

    async def test_two_turns_same_context_complete(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="multiturn", name="Multiturn Agent")

        t1 = await client.post(
            "/a2a/multiturn/v1/message:send",
            json=_message_body("first turn ABC", context_id="ctx-multi"),
            headers=logged_in_headers,
        )
        t2 = await client.post(
            "/a2a/multiturn/v1/message:send",
            json=_message_body("second turn XYZ", context_id="ctx-multi"),
            headers=logged_in_headers,
        )
        assert t1.status_code == 200, t1.text
        assert t2.status_code == 200, t2.text

        task1, task2 = t1.json(), t2.json()
        assert task1["status"]["state"] == "completed"
        assert task2["status"]["state"] == "completed"
        assert task1["id"] != task2["id"]
        assert task1["contextId"] == task2["contextId"] == "ctx-multi"

        # Both turns are listed under the shared context.
        listed = await client.get("/a2a/multiturn/v1/tasks?contextId=ctx-multi", headers=logged_in_headers)
        assert listed.status_code == 200
        ids = {t["id"] for t in listed.json()}
        assert {task1["id"], task2["id"]} <= ids


# ---------------------------------------------------------------------------
# message:stream — real execution
# ---------------------------------------------------------------------------


class TestA2AMessageStreamHTTP:
    """message:stream drives a real execution and emits SSE events."""

    async def test_stream_working_completed_and_output(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="stream-real", name="Stream Agent")

        probe = "StreamProbe-77"
        resp = await client.post(
            "/a2a/stream-real/v1/message:stream",
            json=_message_body(probe, context_id="ctx-stream-real"),
            headers=logged_in_headers,
        )
        assert resp.status_code == 200, resp.text
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = _parse_sse_events(resp.text)
        assert events, "no SSE events received"

        states = [e["status"]["state"] for e in events if e.get("kind") == "status-update"]
        assert "working" in states, states
        assert "completed" in states, states

        streamed_text = "".join(
            part.get("text", "")
            for e in events
            if e.get("kind") == "artifact-update"
            for part in e.get("artifact", {}).get("parts", [])
        )
        assert probe in streamed_text, f"streamed output did not reflect input: {streamed_text!r}"

    async def test_stream_requires_auth(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="stream-auth", name="Stream Auth Agent")
        resp = await client.post(
            "/a2a/stream-auth/v1/message:stream", json=_message_body("hi"), headers=_BAD_AUTH
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestA2AEdgeCasesHTTP:
    """Negative/robustness behaviors over HTTP."""

    async def test_cancel_nonexistent_task_returns_404(self, client: AsyncClient, logged_in_headers):
        await _expose_flow_as_a2a(client, logged_in_headers, slug="cancel-404", name="Cancel 404 Agent")
        resp = await client.post("/a2a/cancel-404/v1/tasks/does-not-exist:cancel", headers=logged_in_headers)
        assert resp.status_code == 404

    async def test_idempotent_retry_does_not_duplicate_task(self, client: AsyncClient, logged_in_headers):
        """Re-sending a completed taskId returns the same task and creates no duplicate."""
        slug = "retry-dupe"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Retry Dupe Agent")

        first = await client.post(
            f"/a2a/{slug}/v1/message:send", json=_message_body("once", context_id="ctx-r"), headers=logged_in_headers
        )
        assert first.status_code == 200
        assert first.json()["status"]["state"] == "completed"
        task_id = first.json()["id"]

        # Re-send the SAME taskId — idempotent retry returns the cached task.
        second = await client.post(
            f"/a2a/{slug}/v1/message:send",
            json=_message_body("once", context_id="ctx-r", task_id=task_id),
            headers=logged_in_headers,
        )
        assert second.status_code == 200
        assert second.json()["id"] == task_id

        # No duplicate task was created for this conversation.
        listing = await client.get(f"/a2a/{slug}/v1/tasks?contextId=ctx-r", headers=logged_in_headers)
        assert listing.status_code == 200
        ids = [t["id"] for t in listing.json()]
        assert ids == [task_id]

    async def test_malformed_message_body_is_handled_gracefully(self, client: AsyncClient, logged_in_headers):
        """Missing/empty message bodies must not 500 the server."""
        slug = "malformed"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Malformed Agent")

        no_message = await client.post(f"/a2a/{slug}/v1/message:send", json={}, headers=logged_in_headers)
        assert no_message.status_code != 500

        empty_parts = await client.post(
            f"/a2a/{slug}/v1/message:send",
            json={"message": {"role": "user", "parts": []}},
            headers=logged_in_headers,
        )
        assert empty_parts.status_code != 500
