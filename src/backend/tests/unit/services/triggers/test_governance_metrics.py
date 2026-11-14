"""Success measures come from durable events, first starts, and renewal intervals."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobEvent, JobStatus
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.deps import session_scope

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("start_event", ["build_start", "RUN_STARTED"])
async def test_metrics_separate_source_replay_test_and_hint_events(make_trigger, owned_flow, start_event):
    from langflow.services.triggers.metrics import query_trigger_metrics

    trigger_id = await make_trigger()
    now = datetime.now(timezone.utc)
    job_id = uuid4()
    async with session_scope() as session:
        session.add(Job(job_id=job_id, flow_id=owned_flow, status=JobStatus.COMPLETED))
        session.add_all(
            [
                JobEvent(job_id=job_id, seq=0, event_type="vertices_sorted", created_at=now - timedelta(seconds=9)),
                JobEvent(job_id=job_id, seq=1, event_type=start_event, created_at=now - timedelta(seconds=8)),
                JobEvent(job_id=job_id, seq=2, event_type=start_event, created_at=now - timedelta(seconds=4)),
            ]
        )
        for key, state, payload, age, job in [
            ("source-complete", "completed", {}, 10, job_id),
            ("source-pending", "pending", {}, 5, None),
            ("replay:copy", "completed", {}, 5, job_id),
            ("test:fake", "completed", {}, 5, job_id),
            ("hint", "completed", {"_source_hint": True}, 5, None),
            ("source-old", "pending", {}, 90, None),
            ("filtered", "skipped", {}, 5, None),
            ("provider-filtered-no-run", "completed", {}, 5, None),
        ]:
            session.add(
                TriggerEvent(
                    trigger_id=trigger_id,
                    dedupe_key=key,
                    state=state,
                    payload=payload,
                    created_at=now - timedelta(seconds=age),
                    job_id=job,
                    attempt=0,
                )
            )
    async with session_scope() as session:
        snapshot = await query_trigger_metrics(session, now=now, window_seconds=60)
    assert snapshot.event_counts[("source", "completed")] == 1
    assert snapshot.event_counts[("source", "pending")] == 1
    assert snapshot.event_counts[("source", "skipped")] == 2
    assert snapshot.event_counts[("replay", "completed")] == 1
    assert snapshot.event_counts[("test", "completed")] == 1
    assert snapshot.dispatch_latencies == [2.0]
    assert snapshot.missing_first_starts == 0
    assert snapshot.oldest_pending_seconds == pytest.approx(90.0)


@pytest.mark.parametrize("protocol", ["langflow", "agui"])
@pytest.mark.parametrize("expose_graph_state", [True, False])
async def test_metrics_observe_real_runner_start_events(
    make_trigger, owned_flow, trigger_owner, protocol, expose_graph_state
):
    from langflow.services.background_execution.live_bus import InMemoryLiveBus
    from langflow.services.background_execution.runner import JobRunner
    from langflow.services.deps import get_job_service
    from langflow.services.triggers.metrics import query_trigger_metrics
    from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
    from sqlmodel import delete

    trigger_id = await make_trigger()
    accepted = datetime.now(timezone.utc) - timedelta(seconds=2)
    job_id = uuid4()
    jobs = get_job_service()
    await jobs.create_job(job_id=job_id, flow_id=owned_flow, user_id=trigger_owner)
    async with session_scope() as session:
        session.add(
            TriggerEvent(
                trigger_id=trigger_id,
                dedupe_key="runner-source",
                state="completed",
                payload={},
                created_at=accepted,
                job_id=job_id,
                attempt=0,
            )
        )
    adapter = get_stream_adapter(
        protocol,
        StreamAdapterContext(run_id=str(job_id), thread_id="t", expose_graph_state=expose_graph_state),
    )

    async def source():
        for event in adapter.initial_events():
            yield event.data_json.encode(), event.type
        for event_type, data in [("vertices_sorted", {"ids": []}), ("build_start", {}), ("end", {})]:
            for event in adapter.translate(event_type, data):
                yield event.data_json.encode(), event.type

    await JobRunner(job_service=jobs, live_bus=InMemoryLiveBus(), adapter=adapter, frame_source=source).run(
        job_id=job_id, source_kwargs={}
    )
    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    events = await jobs.read_events(job_id, after_seq=0)
    start_event = "build_start" if protocol == "langflow" else "RUN_STARTED"
    first_start = next(event for event in events if event.event_type == start_event)
    started = first_start.created_at.replace(tzinfo=timezone.utc)
    async with session_scope() as session:
        snapshot = await query_trigger_metrics(session, now=datetime.now(timezone.utc), window_seconds=60)
    assert snapshot.dispatch_latencies == [pytest.approx((started - accepted).total_seconds())]
    assert snapshot.dispatch_latencies[0] >= 2
    assert snapshot.missing_first_starts == 0

    async with session_scope() as session:
        await session.exec(delete(JobEvent).where(JobEvent.job_id == job_id, JobEvent.event_type == start_event))
    async with session_scope() as session:
        snapshot = await query_trigger_metrics(session, now=datetime.now(timezone.utc), window_seconds=60)
    assert snapshot.dispatch_latencies == []
    assert snapshot.missing_first_starts == 1


async def test_renewal_metrics_keep_previous_and_new_expiry_intervals(make_trigger):
    from langflow.services.database.models.trigger.model import TriggerRenewalObservation
    from langflow.services.triggers.metrics import query_trigger_metrics

    trigger_id = await make_trigger()
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        for outcome, gap in [("renewed", 0.0), ("renewed", 12.0), ("failed", 0.0)]:
            session.add(
                TriggerRenewalObservation(
                    trigger_id=trigger_id,
                    subscription_id=uuid4(),
                    observed_at=now,
                    previous_expires_at=now - timedelta(seconds=gap),
                    expires_at=now + timedelta(hours=1) if outcome == "renewed" else None,
                    outcome=outcome,
                    gap_seconds=gap,
                )
            )
    async with session_scope() as session:
        snapshot = await query_trigger_metrics(session, now=now, window_seconds=60)
    assert snapshot.renewal_counts == {"renewed": 2, "failed": 1}
    assert snapshot.renewals_with_gap == 1
    assert snapshot.renewal_gap_seconds == 12.0
