"""What the dispatcher does with a claimed ledger row.

These are the ticket's operator guarantees: one job per event, retries with a
growing backoff, a dead letter at the attempt limit, a pin that survives a flow
edit, and a binding that is reported rather than silently rewritten.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import (
    TriggerBindingTarget,
    TriggerEventState,
    TriggerState,
)
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, ledger
from langflow.services.triggers.constants import TRIGGER_EVENT_FIELD

pytestmark = pytest.mark.no_blockbuster


async def _append(trigger_id, dedupe_key: str = "e1", payload: dict | None = None):
    async with session_scope() as session:
        event, _ = await ledger.append_event(
            session, trigger_id=trigger_id, dedupe_key=dedupe_key, payload=payload or {}
        )
        return event.id


async def _event(event_id) -> TriggerEvent:
    async with session_scope() as session:
        return await session.get(TriggerEvent, event_id)


async def test_one_event_becomes_exactly_one_job(make_trigger, fake_background_service) -> None:
    trigger_id = await make_trigger(node_id="ScheduleTrigger-abc12")
    event_id = await _append(trigger_id, payload={"scheduled_at": "2026-09-07T08:00:00+00:00"})

    dispatched = await dispatcher.run_once(owner="solo")
    assert dispatched == 1
    assert len(fake_background_service.submits) == 1

    row = await _event(event_id)
    assert row.state == TriggerEventState.DISPATCHED.value
    assert row.job_id is not None
    assert row.session_id == f"trigger:{trigger_id}:{event_id}"
    # The lease is dropped once a job exists: liveness now belongs to the job.
    assert row.lease_owner is None
    assert row.lease_expires_at is None

    request = fake_background_service.submits[0]["request"]
    assert request["idempotency_key"] == f"trg:{event_id}:0"
    # The firing event rides tweaks, keyed by the trigger's canvas node, and it
    # is a JSON string because that is what the component's template field
    # holds. The fake service parsed this request through the real
    # WorkflowRunRequest before recording it.
    event = json.loads(request["tweaks"]["ScheduleTrigger-abc12"][TRIGGER_EVENT_FIELD])
    assert event["event_id"] == str(event_id)
    assert event["kind"] == "schedule"
    assert event["payload"] == {"scheduled_at": "2026-09-07T08:00:00+00:00"}
    # A run request may not carry keys WorkflowRunRequest does not declare.
    assert "trigger_event" not in request
    assert "execution_family" not in request
    # Nothing was pinned, so no canvas copy rides the job row.
    assert "data" not in request

    # A second pass has nothing left to claim.
    assert await dispatcher.run_once(owner="solo") == 0
    assert len(fake_background_service.submits) == 1


async def test_the_per_trigger_concurrency_cap_holds_events_back(make_trigger, fake_background_service) -> None:
    trigger_id = await make_trigger(concurrency_limit=1)
    await _append(trigger_id, "a")
    await _append(trigger_id, "b")

    assert await dispatcher.run_once(owner="solo") == 1
    assert len(fake_background_service.submits) == 1

    # Still capped while the first run is in flight.
    assert await dispatcher.run_once(owner="solo") == 0

    async with session_scope() as session:
        dispatched = (await session.exec(_select_events(session, trigger_id, TriggerEventState.DISPATCHED.value))).all()
        for row in dispatched:
            row.state = TriggerEventState.COMPLETED.value
            session.add(row)

    assert await dispatcher.run_once(owner="solo") == 1
    assert len(fake_background_service.submits) == 2


def _select_events(session, trigger_id, state):  # noqa: ARG001
    from sqlmodel import select

    return select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id, TriggerEvent.state == state)


async def test_a_failed_submit_retries_with_backoff_then_dead_letters(make_trigger, monkeypatch) -> None:
    """Attempts grow, the row waits longer each time, and the limit is terminal."""
    from .conftest import FakeBackgroundExecutionService

    service = FakeBackgroundExecutionService(fail_times=99)
    monkeypatch.setattr("langflow.services.deps.get_background_execution_service", lambda: service)

    trigger_id = await make_trigger(max_attempts=3)
    event_id = await _append(trigger_id)

    await dispatcher.run_once(owner="solo")
    row = await _event(event_id)
    assert row.state == TriggerEventState.PENDING.value
    assert row.attempt == 1
    assert row.error.startswith("submit_failed:")
    first_delay = row.available_at

    # The row is not due yet, so a poll finds nothing.
    assert await dispatcher.run_once(owner="solo") == 0

    await _make_due(event_id)
    await dispatcher.run_once(owner="solo")
    row = await _event(event_id)
    assert row.attempt == 2
    assert row.state == TriggerEventState.PENDING.value
    assert _aware(row.available_at) > _aware(first_delay)

    await _make_due(event_id)
    await dispatcher.run_once(owner="solo")
    row = await _event(event_id)
    assert row.state == TriggerEventState.DEAD.value
    assert row.attempt == 3

    # A dead row is never claimed again.
    assert await dispatcher.run_once(owner="solo") == 0


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _make_due(event_id) -> None:
    async with session_scope() as session:
        row = await session.get(TriggerEvent, event_id)
        row.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(row)


async def test_a_dispatcher_killed_mid_claim_releases_the_lease_and_retries(
    make_trigger, fake_background_service
) -> None:
    """The kill-mid-claim story: expiry returns the row with attempt incremented."""
    trigger_id = await make_trigger(max_attempts=2)
    event_id = await _append(trigger_id)

    async with session_scope() as session:
        claimed = await dispatcher.claim_batch(session, owner="doomed", limit=5, lease_ttl_s=60)
        assert [row.id for row in claimed] == [event_id]
        # Simulate the holder dying: the lease is in the past, nothing else changed.
        row = await session.get(TriggerEvent, event_id)
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(row)

    async with session_scope() as session:
        assert await dispatcher.sweep_expired_claims(session) == 1

    row = await _event(event_id)
    assert row.state == TriggerEventState.PENDING.value
    assert row.attempt == 1
    assert row.error == "lease_expired"
    assert row.lease_owner is None

    await _make_due(event_id)
    assert await dispatcher.run_once(owner="survivor") == 1
    assert len(fake_background_service.submits) == 1
    # The retry mints a NEW idempotency key, or the background service would
    # hand back the dead attempt's job id and the event would never re-run.
    assert fake_background_service.submits[0]["request"]["idempotency_key"] == f"trg:{event_id}:1"


async def test_a_dispatched_row_is_never_swept(make_trigger, fake_background_service) -> None:
    """Once a job exists, re-dispatching would double the run the ledger exists to protect."""
    trigger_id = await make_trigger()
    event_id = await _append(trigger_id)
    await dispatcher.run_once(owner="solo")

    async with session_scope() as session:
        row = await session.get(TriggerEvent, event_id)
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.add(row)

    async with session_scope() as session:
        assert await dispatcher.sweep_expired_claims(session) == 0
    assert (await _event(event_id)).state == TriggerEventState.DISPATCHED.value
    assert len(fake_background_service.submits) == 1


async def test_a_paused_trigger_retires_its_queued_events(make_trigger, fake_background_service) -> None:
    trigger_id = await make_trigger(state=TriggerState.PAUSED.value)
    event_id = await _append(trigger_id)

    assert await dispatcher.run_once(owner="solo") == 0
    assert fake_background_service.submits == []
    row = await _event(event_id)
    assert row.state == TriggerEventState.FAILED.value
    assert row.error == "trigger_paused"


async def test_a_pinned_trigger_runs_the_pinned_canvas(make_trigger, fake_background_service) -> None:
    """A pin decides what runs; editing the flow afterwards does not change it."""
    pinned_data = {"nodes": [{"id": "pinned-node"}], "edges": []}
    trigger_id = await make_trigger()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        version = FlowVersion(flow_id=trigger.flow_id, user_id=trigger.user_id, data=pinned_data, version_number=1)
        session.add(version)
        await session.flush()
        trigger.flow_version_id = version.id
        session.add(trigger)
        flow = await session.get(Flow, trigger.flow_id)
        flow.data = {"nodes": [{"id": "edited-after-the-pin"}], "edges": []}
        session.add(flow)

    await _append(trigger_id)
    assert await dispatcher.run_once(owner="solo") == 1
    assert fake_background_service.submits[0]["request"]["data"] == pinned_data


async def test_a_deployment_binding_is_reported_not_silently_run_as_a_flow(
    make_trigger, fake_background_service
) -> None:
    trigger_id = await make_trigger(binding_target=TriggerBindingTarget.DEPLOYMENT.value)
    event_id = await _append(trigger_id)

    assert await dispatcher.run_once(owner="solo") == 0
    assert fake_background_service.submits == []
    row = await _event(event_id)
    assert row.state == TriggerEventState.FAILED.value
    assert "not dispatched" in row.error

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert "not dispatched" in trigger.last_error


async def test_a_finished_job_closes_its_ledger_row(make_trigger, fake_background_service) -> None:  # noqa: ARG001
    """An operator can tell a finished trigger run from a stuck one."""
    trigger_id = await make_trigger()
    event_id = await _append(trigger_id)
    await dispatcher.run_once(owner="solo")
    row = await _event(event_id)

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        session.add(
            Job(
                job_id=row.job_id,
                flow_id=trigger.flow_id,
                user_id=trigger.user_id,
                status=JobStatus.COMPLETED,
                type=JobType.WORKFLOW,
            )
        )

    async with session_scope() as session:
        assert await dispatcher.reconcile_dispatched(session) == 1
    assert (await _event(event_id)).state == TriggerEventState.COMPLETED.value


@pytest.mark.parametrize("pinned", [False, True])
def test_the_submit_request_is_a_valid_workflow_run_request(pinned) -> None:
    """The request the dispatcher builds must survive the worker's re-parse.

    ``BackgroundExecutionService.submit`` commits the job row and then hands the
    request to the frame-source factory, which rebuilds a ``WorkflowRunRequest``
    — a model that forbids extra keys. A key the model does not declare
    therefore fails the run *after* the job exists, and the event retries its way
    to a dead letter while orphan QUEUED job rows pile up. No recorder can see
    that, so the parser itself is the assertion here.
    """
    from uuid import uuid4

    from langflow.api.v2.workflow import _parse_persisted_workflow_request

    trigger = Trigger(
        flow_id=uuid4(),
        user_id=uuid4(),
        name="digest",
        kind="schedule",
        node_id="ScheduleTrigger-1",
        config={},
        provider_state={},
        concurrency_limit=1,
        max_attempts=5,
    )
    event = TriggerEvent(trigger_id=trigger.id, dedupe_key="tick:1", payload={"scheduled_at": "2026-09-07T08:00:00Z"})
    request = dispatcher.build_submit_request(
        trigger=trigger,
        event=event,
        binding_data={"nodes": [], "edges": []} if pinned else None,
    )

    parsed = _parse_persisted_workflow_request(request)
    assert parsed.flow_id == str(trigger.flow_id)
    assert parsed.mode == "background"
    assert parsed.session_id == request["session_id"]
    assert json.loads(parsed.tweaks["ScheduleTrigger-1"][TRIGGER_EVENT_FIELD])["event_id"] == str(event.id)
    assert (parsed.data is not None) is pinned
