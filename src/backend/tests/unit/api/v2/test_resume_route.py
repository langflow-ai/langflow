"""HTTP resume route (LE-1450): POST /api/v2/workflows/{job_id}/resume.

Route-level tests against a hand-written SUSPENDED job row (the full HTTP
round-trip gates on a real pausing flow): owner-or-superuser auth with
deny-to-404, single-use 409, and accepted-resume 200.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobEvent, JobStatus, JobType
from lfx.services.deps import session_scope

pytestmark = pytest.mark.usefixtures("client")


def _headers(api_key) -> dict:
    return {"x-api-key": api_key.api_key}


@pytest.fixture
async def suspended_job(created_api_key):
    """A hand-written SUSPENDED workflow job owned by the api-key user, with a real flow."""
    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    request = {"flow_id": str(flow_id), "mode": "background", "stream_protocol": "langflow", "input_value": "hi"}
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user_id,
                type=JobType.WORKFLOW,
                status=JobStatus.SUSPENDED,
                job_metadata={"pending_request_id": "req-1", "request": request},
            )
        )
        await session.flush()
    yield job_id
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job:
            await session.delete(job)
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def test_resume_owner_accepts_200(client, created_api_key, suspended_job):
    body = {"request_id": "req-1", "decision": {"action_id": "approve"}}
    resp = await client.post(f"api/v2/workflows/{suspended_job}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 200
    assert resp.json()["status"] == "resuming"


async def test_resume_stale_request_id_409(client, created_api_key, suspended_job):
    body = {"request_id": "WRONG", "decision": {"action_id": "approve"}}
    resp = await client.post(f"api/v2/workflows/{suspended_job}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 409


async def test_resume_unknown_job_404(client, created_api_key):
    body = {"request_id": "req-1", "decision": {}}
    resp = await client.post(f"api/v2/workflows/{uuid4()}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 404


async def test_resume_non_suspended_job_409(client, created_api_key):
    """A QUEUED (not suspended) job is not resumable → 409."""
    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(
            Job(job_id=job_id, flow_id=flow_id, user_id=user_id, type=JobType.WORKFLOW, status=JobStatus.QUEUED)
        )
        await session.flush()
    try:
        body = {"request_id": "req-1", "decision": {}}
        resp = await client.post(f"api/v2/workflows/{job_id}/resume", json=body, headers=_headers(created_api_key))
        assert resp.status_code == 409
    finally:
        async with session_scope() as session:
            for model, key in ((Job, job_id), (Flow, flow_id)):
                row = await session.get(model, key)
                if row:
                    await session.delete(row)


async def test_resume_invalid_job_id_404(client, created_api_key):
    body = {"request_id": "req-1", "decision": {}}
    resp = await client.post("api/v2/workflows/not-a-uuid/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 404


@pytest.fixture
async def suspended_job_with_decisions(created_api_key):
    """A SUSPENDED job whose pending request constrains the choice to approve/reject."""
    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    request = {"flow_id": str(flow_id), "mode": "background", "stream_protocol": "langflow", "input_value": "hi"}
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user_id,
                type=JobType.WORKFLOW,
                status=JobStatus.SUSPENDED,
                job_metadata={"pending_request_id": "req-1", "request": request},
            )
        )
        session.add(
            JobEvent(
                job_id=job_id,
                seq=1,
                event_type="human_input_required",
                payload={"request_id": "req-1", "allowed_decisions": ["approve", "reject"]},
            )
        )
        await session.flush()
    yield job_id
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job:
            await session.delete(job)
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def test_resume_action_id_not_allowed_422(client, created_api_key, suspended_job_with_decisions):
    """B1: a decision whose action_id is not in allowed_decisions is rejected with 422."""
    body = {"request_id": "req-1", "decision": {"action_id": "delete_everything"}}
    resp = await client.post(
        f"api/v2/workflows/{suspended_job_with_decisions}/resume", json=body, headers=_headers(created_api_key)
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "INVALID_DECISION"


async def test_resume_allowed_action_id_accepted_200(client, created_api_key, suspended_job_with_decisions):
    """B1: a decision whose action_id is in allowed_decisions passes validation."""
    body = {"request_id": "req-1", "decision": {"action_id": "approve"}}
    resp = await client.post(
        f"api/v2/workflows/{suspended_job_with_decisions}/resume", json=body, headers=_headers(created_api_key)
    )
    assert resp.status_code == 200, resp.text


async def test_mark_card_answered_is_noop_without_card_message(client):  # noqa: ARG001
    """mark_card_answered degrades gracefully when no card message id is recorded."""
    from langflow.api.v2.hitl import mark_card_answered

    # Unknown job → no job_metadata.card_message_id → returns without raising.
    await mark_card_answered(uuid4(), "req-1", {"action_id": "approve"})


async def test_resume_reenforces_flow_execute_permission(client, created_api_key, suspended_job, monkeypatch):
    """Resume executes the rest of the flow, so flow:execute is re-checked at resume time.

    Job ownership alone must not be enough: shared access revoked while the run was
    suspended (a plugin-enforced deny) has to block the decision and keep the job SUSPENDED.
    """
    import langflow.services.authorization as authz
    from fastapi import HTTPException

    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="flow:execute denied")

    monkeypatch.setattr(authz, "ensure_flow_permission", _deny)
    body = {"request_id": "req-1", "decision": {"action_id": "approve"}}
    resp = await client.post(f"api/v2/workflows/{suspended_job}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 403, resp.text
    async with session_scope() as session:
        job = await session.get(Job, suspended_job)
        assert job.status == JobStatus.SUSPENDED


def _card_row(flow_id, request_id: str):
    from langflow.services.database.models.message.model import MessageTable

    return MessageTable(
        flow_id=flow_id,
        session_id="sess-cards",
        sender="Machine",
        sender_name="AI",
        text="",
        files=[],
        category="message",
        content_blocks=[
            {
                "title": "Human input required",
                "contents": [{"type": "human_input", "request_id": request_id, "options": []}],
            }
        ],
    )


async def test_mark_card_answered_stamps_snapshot_card_not_next_pause(client, created_api_key):  # noqa: ARG001
    """The decision stamps the card captured before resume, never a later pause's card.

    Simulates the race: the continuation already reached a second pause and overwrote
    job_metadata.card_message_id, but the caller passes the pre-resume snapshot id.
    """
    from langflow.api.v2.hitl import mark_card_answered
    from langflow.services.database.models.message.model import MessageTable

    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    first_card, second_card = _card_row(flow_id, "req-1"), _card_row(flow_id, "req-2")
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(first_card)
        session.add(second_card)
        await session.flush()
        first_id, second_id = first_card.id, second_card.id
        session.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user_id,
                type=JobType.WORKFLOW,
                status=JobStatus.SUSPENDED,
                job_metadata={"card_message_id": str(second_id)},
            )
        )
        await session.flush()
    try:
        await mark_card_answered(job_id, "req-1", {"action_id": "approve"}, card_message_id=str(first_id))
        async with session_scope() as session:
            first = await session.get(MessageTable, first_id)
            second = await session.get(MessageTable, second_id)
            assert first.content_blocks[0]["contents"][0]["submitted_action"] == "approve"
            assert "submitted_action" not in second.content_blocks[0]["contents"][0]
    finally:
        async with session_scope() as session:
            for model, key in ((Job, job_id), (MessageTable, first_id), (MessageTable, second_id), (Flow, flow_id)):
                row = await session.get(model, key)
                if row:
                    await session.delete(row)


async def test_mark_card_answered_skips_card_of_a_different_request(client, created_api_key):  # noqa: ARG001
    """Even a stale card_message_id cannot stamp a card whose request_id differs."""
    from langflow.api.v2.hitl import mark_card_answered
    from langflow.services.database.models.message.model import MessageTable

    user_id = created_api_key.user_id
    flow_id = uuid4()
    other_card = _card_row(flow_id, "req-2")
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(other_card)
        await session.flush()
        other_id = other_card.id
    try:
        await mark_card_answered(uuid4(), "req-1", {"action_id": "approve"}, card_message_id=str(other_id))
        async with session_scope() as session:
            other = await session.get(MessageTable, other_id)
            assert "submitted_action" not in other.content_blocks[0]["contents"][0]
    finally:
        async with session_scope() as session:
            for model, key in ((MessageTable, other_id), (Flow, flow_id)):
                row = await session.get(model, key)
                if row:
                    await session.delete(row)


async def test_list_pending_returns_suspended_hitl(client, created_api_key):
    """GET /workflows/pending surfaces a SUSPENDED HITL job + its pending request."""
    from sqlmodel import select

    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    request = {"flow_id": str(flow_id), "session_id": "sess-pending", "input_value": "hi"}
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user_id,
                type=JobType.WORKFLOW,
                status=JobStatus.SUSPENDED,
                job_metadata={"pending_request_id": "req-1", "request": request},
            )
        )
        session.add(
            JobEvent(
                job_id=job_id,
                seq=1,
                event_type="human_input_required",
                payload={
                    "request_id": "req-1",
                    "prompt": "Approve?",
                    "kind": "tool_approval",
                    "options": [{"action_id": "approve", "label": "Approve"}],
                    "allowed_decisions": ["approve", "reject"],
                },
            )
        )
        await session.flush()
    try:
        resp = await client.get(f"api/v2/workflows/pending?flow_id={flow_id}", headers=_headers(created_api_key))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["job_id"] == str(job_id)
        assert item["session_id"] == "sess-pending"
        assert item["request_id"] == "req-1"
        assert item["prompt"] == "Approve?"
        assert item["allowed_decisions"] == ["approve", "reject"]
    finally:
        async with session_scope() as session:
            events = (await session.exec(select(JobEvent).where(JobEvent.job_id == job_id))).all()
            for event in events:
                await session.delete(event)
            for model, key in ((Job, job_id), (Flow, flow_id)):
                row = await session.get(model, key)
                if row:
                    await session.delete(row)


class TestRerouteDecisionOnTimeout:
    """Lazy timeout reroute (no watchdog): a late decision goes to fallback only if defined."""

    @staticmethod
    def _pending(*, seconds_ago: float, timeout_s: int, fallback: str | None):
        from datetime import datetime, timedelta, timezone

        paused_at = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()
        return {"timeout_seconds": timeout_s, "fallback_action": fallback, "paused_at": paused_at}

    def test_late_decision_reroutes_to_fallback(self):
        from langflow.api.v2.hitl import reroute_decision_on_timeout

        pending = self._pending(seconds_ago=120, timeout_s=60, fallback="fallback")
        result = reroute_decision_on_timeout(pending, {"action_id": "approve", "values": {}})
        assert result["action_id"] == "fallback"
        assert result["values"] == {}

    def test_within_deadline_keeps_decision(self):
        from langflow.api.v2.hitl import reroute_decision_on_timeout

        pending = self._pending(seconds_ago=5, timeout_s=60, fallback="fallback")
        assert reroute_decision_on_timeout(pending, {"action_id": "approve"})["action_id"] == "approve"

    def test_late_but_no_fallback_expires_decision(self):
        """A late answer with no fallback expires to a sentinel so no branch is taken."""
        from langflow.api.v2.hitl import reroute_decision_on_timeout
        from lfx.run.hitl import EXPIRED_ACTION

        pending = self._pending(seconds_ago=120, timeout_s=60, fallback=None)
        assert reroute_decision_on_timeout(pending, {"action_id": "approve"})["action_id"] == EXPIRED_ACTION

    def test_no_timeout_keeps_decision(self):
        from langflow.api.v2.hitl import reroute_decision_on_timeout

        pending = self._pending(seconds_ago=120, timeout_s=0, fallback="fallback")
        assert reroute_decision_on_timeout(pending, {"action_id": "approve"})["action_id"] == "approve"


class TestUnwrapPausePayload:
    """The stored pause payload is the wire frame; consumers need the raw request unwrapped."""

    def test_flat_payload_passthrough(self):
        from langflow.services.jobs.service import _unwrap_pause_payload

        flat = {"request_id": "r", "timeout_seconds": 60, "allowed_decisions": ["approve"]}
        assert _unwrap_pause_payload(flat) is flat

    def test_langflow_envelope_unwrapped(self):
        from langflow.services.jobs.service import _unwrap_pause_payload

        raw = {"request_id": "r", "timeout_seconds": 60, "fallback_action": "fallback"}
        wrapped = {"event": "human_input_required", "data": raw}
        assert _unwrap_pause_payload(wrapped) == raw

    def test_agui_custom_event_unwrapped(self):
        from langflow.services.jobs.service import _unwrap_pause_payload

        raw = {"request_id": "r", "timeout_seconds": 60, "fallback_action": "fallback"}
        wrapped = {"type": "CUSTOM", "name": "langflow.human_input_required", "value": raw}
        assert _unwrap_pause_payload(wrapped) == raw

    def test_reroute_reads_timeout_through_agui_envelope(self):
        """End-to-end: a wrapped AG-UI payload (what production stores) still triggers reroute."""
        from datetime import datetime, timedelta, timezone

        from langflow.api.v2.hitl import reroute_decision_on_timeout
        from langflow.services.jobs.service import _unwrap_pause_payload

        paused_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        raw = {"request_id": "r", "timeout_seconds": 60, "fallback_action": "fallback", "paused_at": paused_at}
        stored = {"type": "CUSTOM", "name": "langflow.human_input_required", "value": raw}
        pending = _unwrap_pause_payload(stored)
        assert reroute_decision_on_timeout(pending, {"action_id": "approve"})["action_id"] == "fallback"
