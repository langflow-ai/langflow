"""Durable background mode on bare ``lfx serve`` (LE-1695).

Real-integration tests through the FastAPI surface: with ``LFX_SERVE_DURABLE_DB``
set, ``POST /api/v2/workflows`` accepts ``mode="background"``, a HITL flow suspends
into the SQLite job store, and ``POST /{job_id}/resume`` completes the chosen branch —
including after a "process restart" (a fresh app + host on the same DB file).
"""

import contextlib
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph.checkpoint.store import set_default_checkpoint_store

_ECHO_FLOW_ID = "67ccd2be-17f0-4190-81ff-3bb2cf6508e6"
_HITL_FLOW_ID = "aaccd2be-17f0-4190-81ff-3bb2cf6508e6"
_API_KEY = "test-key"  # pragma: allowlist secret
_HEADERS = {"x-api-key": _API_KEY}
_WAIT_S = 20.0


def _echo_graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    return graph


def _node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str, handle: str, field: str = "input_value") -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{handle}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": handle, "output_types": ["Message"]},
            "targetHandle": {"fieldName": field, "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


def _pausing_graph() -> Graph:
    payload = {
        "nodes": [
            _node(ChatInput(_id="chat_input")),
            _node(HumanInput(_id="hitl1")),
            _node(ChatOutput(_id="co_approve")),
            _node(ChatOutput(_id="co_reject")),
        ],
        "edges": [
            _edge("chat_input", "hitl1", "message", field="prompt"),
            _edge("hitl1", "co_approve", "branch_approve"),
            _edge("hitl1", "co_reject", "branch_reject"),
        ],
    }
    graph = Graph.from_payload(payload, flow_id=_HITL_FLOW_ID)
    graph.prepare()
    return graph


def _build_registry() -> FlowRegistry:
    registry = FlowRegistry()
    registry.add(
        _echo_graph(),
        FlowMeta(id=_ECHO_FLOW_ID, relative_path=f"{_ECHO_FLOW_ID}.json", title="echo", description=None),
    )
    registry.add(
        _pausing_graph(),
        FlowMeta(id=_HITL_FLOW_ID, relative_path=f"{_HITL_FLOW_ID}.json", title="hitl", description=None),
    )
    return registry


@pytest.fixture(autouse=True)
def _reset_default_checkpoint_store():
    """The durable host installs its store as the module fallback; undo it per test."""
    yield
    set_default_checkpoint_store(None)


@pytest.fixture
def durable_db(tmp_path, monkeypatch):
    db_path = tmp_path / "serve-durable.db"
    monkeypatch.setenv("LANGFLOW_API_KEY", _API_KEY)
    monkeypatch.setenv("LFX_SERVE_DURABLE_DB", str(db_path))
    return db_path


@pytest.fixture
def client(durable_db):
    del durable_db
    app = create_multi_serve_app(registry=_build_registry())
    with TestClient(app) as test_client:
        yield test_client


def _get_status(client: TestClient, job_id: str) -> dict:
    resp = client.get("/api/v2/workflows", params={"job_id": job_id}, headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _wait_for_status(client: TestClient, job_id: str, wanted: str) -> dict:
    deadline = time.monotonic() + _WAIT_S
    body = {}
    while time.monotonic() < deadline:
        body = _get_status(client, job_id)
        if body["status"] == wanted:
            return body
        assert body["status"] not in {"failed", "cancelled"}, body
        time.sleep(0.05)
    msg = f"job {job_id} never reached {wanted}; last: {body}"
    raise AssertionError(msg)


def _submit(client: TestClient, flow_id: str, input_value: str = "hello") -> str:
    resp = client.post(
        "/api/v2/workflows",
        json={"flow_id": flow_id, "input_value": input_value, "mode": "background"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    return body["job_id"]


def _pending_request(client: TestClient, job_id: str) -> dict:
    resp = client.get(f"/api/v2/workflows/{job_id}/pending", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _read_events(client: TestClient, job_id: str, *, last_event_id: str | None = None) -> list[dict]:
    headers = dict(_HEADERS)
    if last_event_id is not None:
        headers["Last-Event-ID"] = last_event_id
    resp = client.get(f"/api/v2/workflows/{job_id}/events", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    events: list[dict] = []
    for block in resp.text.split("\n\n"):
        data_line = next((line for line in block.splitlines() if line.startswith("data:")), None)
        if data_line:
            events.append(json.loads(data_line[len("data:") :].strip()))
    return events


def test_background_echo_completes_with_execution_response(client):
    job_id = _submit(client, _ECHO_FLOW_ID)
    body = _wait_for_status(client, job_id, "completed")
    assert body["flow_id"] == _ECHO_FLOW_ID
    assert "hello" in (body["output"]["text"] or "")
    assert body["outputs"]


def test_background_hitl_suspends_and_exposes_pending_request(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    body = _wait_for_status(client, job_id, "suspended")
    assert body["object"] == "job"
    pending = _pending_request(client, job_id)
    assert pending["request_id"]
    assert any(option.get("action_id") == "approve" for option in pending.get("options", []))


def test_resubmit_supersedes_the_stale_suspended_run(client):
    """Re-running a paused flow cancels the stale pause and tracks only the new one."""
    stale_job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, stale_job_id, "suspended")
    stale_request_id = _pending_request(client, stale_job_id)["request_id"]

    new_job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, new_job_id, "suspended")

    stale = _get_status(client, stale_job_id)
    assert stale["status"] == "cancelled"
    resp = client.get(f"/api/v2/workflows/{stale_job_id}/pending", headers=_HEADERS)
    assert resp.status_code == 404
    pending = _pending_request(client, new_job_id)
    assert pending["request_id"]
    assert pending["request_id"] != stale_request_id


def test_resubmit_of_a_different_flow_leaves_the_pause_alone(client):
    suspended_job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, suspended_job_id, "suspended")

    other_job_id = _submit(client, _ECHO_FLOW_ID)
    _wait_for_status(client, other_job_id, "completed")

    assert _get_status(client, suspended_job_id)["status"] == "suspended"
    assert _pending_request(client, suspended_job_id)["request_id"]


def test_resume_completes_only_the_chosen_branch(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    pending = _pending_request(client, job_id)

    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": pending["request_id"], "decision": {"action_id": "approve", "values": {}}},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "resuming"

    body = _wait_for_status(client, job_id, "completed")
    assert "co_approve" in body["outputs"]
    assert "co_reject" not in body["outputs"]


@pytest.mark.usefixtures("durable_db")
def test_resume_survives_process_restart():
    app = create_multi_serve_app(registry=_build_registry())
    with TestClient(app) as first_client:
        job_id = _submit(first_client, _HITL_FLOW_ID)
        _wait_for_status(first_client, job_id, "suspended")
        pending = _pending_request(first_client, job_id)

    restarted_app = create_multi_serve_app(registry=_build_registry())
    with TestClient(restarted_app) as second_client:
        assert _get_status(second_client, job_id)["status"] == "suspended"
        resp = second_client.post(
            f"/api/v2/workflows/{job_id}/resume",
            json={"request_id": pending["request_id"], "decision": {"action_id": "approve", "values": {}}},
            headers=_HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = _wait_for_status(second_client, job_id, "completed")
        assert "co_approve" in body["outputs"]
        assert "co_reject" not in body["outputs"]


def _backdate_pause(db_path, job_id: str, *, days: int) -> None:
    """Rewrite the suspended job's ``paused_at`` so the pending request is already expired."""
    stale = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        row = conn.execute("SELECT job_metadata FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        meta = json.loads(row[0])
        meta["pending"]["paused_at"] = stale
        conn.execute("UPDATE jobs SET job_metadata = ? WHERE job_id = ?", (json.dumps(meta), job_id))


def test_late_resume_records_human_input_expired_event(client, durable_db):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    pending = _pending_request(client, job_id)
    _backdate_pause(durable_db, job_id, days=10)

    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": pending["request_id"], "decision": {"action_id": "approve", "values": {}}},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    body = _wait_for_status(client, job_id, "completed")
    assert body["outputs"] == {}, "expired with no fallback takes no branch"

    events = _read_events(client, job_id)
    expired = [event for event in events if event["event"] == "human_input_expired"]
    assert expired, f"no human_input_expired event; got {[e['event'] for e in events]}"
    payload = expired[0]["data"]
    assert payload["request_id"] == pending["request_id"]
    assert payload["requested_action"] == "approve"
    assert payload["rerouted_to"] == "__expired__"

    decision_events = [event for event in events if event["event"] == "human_input_decision"]
    assert decision_events
    assert decision_events[0]["data"]["action_id"] == "__expired__"
    assert expired[0]["seq"] < decision_events[0]["seq"]


def test_ontime_resume_records_no_expired_event(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    pending = _pending_request(client, job_id)

    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": pending["request_id"], "decision": {"action_id": "approve", "values": {}}},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    _wait_for_status(client, job_id, "completed")

    events = _read_events(client, job_id)
    assert not [event for event in events if event["event"] == "human_input_expired"]


def test_events_endpoint_replays_completed_run(client):
    job_id = _submit(client, _ECHO_FLOW_ID)
    _wait_for_status(client, job_id, "completed")
    events = _read_events(client, job_id)
    assert events, "expected at least the terminal 'end' event"
    assert any(event["event"] == "end" for event in events)
    assert all(event["seq"] >= 1 for event in events)


def test_events_endpoint_streams_hitl_request_and_ends_at_suspend(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    events = _read_events(client, job_id)
    request_events = [event for event in events if event["event"] == "human_input_request"]
    assert request_events, events
    assert request_events[0]["data"].get("request_id")


def test_events_endpoint_resumes_from_last_event_id_after_resume(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    pending = _pending_request(client, job_id)

    before = _read_events(client, job_id)
    assert before
    last_seq = str(before[-1]["seq"])

    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": pending["request_id"], "decision": {"action_id": "approve", "values": {}}},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    _wait_for_status(client, job_id, "completed")

    after = _read_events(client, job_id, last_event_id=last_seq)
    assert after, "reconnect from Last-Event-ID should deliver post-resume events"
    assert all(event["seq"] > int(last_seq) for event in after)
    assert any(event["event"] == "human_input_decision" for event in after)
    assert any(event["event"] == "end" for event in after)


def test_events_endpoint_unknown_job_404(client):
    resp = client.get(
        "/api/v2/workflows/00000000-0000-4000-8000-000000000000/events",
        headers=_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "JOB_NOT_FOUND"


def test_events_endpoint_requires_api_key(client):
    job_id = _submit(client, _ECHO_FLOW_ID)
    _wait_for_status(client, job_id, "completed")
    resp = client.get(f"/api/v2/workflows/{job_id}/events")
    assert resp.status_code == 401


def test_resume_unknown_job_404(client):
    resp = client.post(
        "/api/v2/workflows/00000000-0000-4000-8000-000000000000/resume",
        json={"request_id": "whatever", "decision": {"action_id": "approve"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "JOB_NOT_FOUND"


def test_resume_disallowed_decision_422(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    pending = _pending_request(client, job_id)
    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": pending["request_id"], "decision": {"action_id": "not-a-real-option"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_DECISION"
    assert _get_status(client, job_id)["status"] == "suspended"


def test_resume_stale_request_id_409(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": "stale-id", "decision": {"action_id": "approve"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NOT_RESUMABLE"


def test_resume_completed_job_409(client):
    job_id = _submit(client, _ECHO_FLOW_ID)
    _wait_for_status(client, job_id, "completed")
    resp = client.post(
        f"/api/v2/workflows/{job_id}/resume",
        json={"request_id": "anything", "decision": {"action_id": "approve"}},
        headers=_HEADERS,
    )
    assert resp.status_code == 409


def test_stop_suspended_job_cancels(client):
    job_id = _submit(client, _HITL_FLOW_ID)
    _wait_for_status(client, job_id, "suspended")
    resp = client.post(
        "/api/v2/workflows/stop",
        json={"job_id": job_id},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert _get_status(client, job_id)["status"] == "cancelled"


def test_background_requires_api_key(client):
    resp = client.post(
        "/api/v2/workflows",
        json={"flow_id": _ECHO_FLOW_ID, "input_value": "x", "mode": "background"},
    )
    assert resp.status_code == 401
