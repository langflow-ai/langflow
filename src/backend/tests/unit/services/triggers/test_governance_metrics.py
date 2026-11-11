"""Success measures come from durable events, first starts, and renewal intervals."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobEvent, JobStatus
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.deps import session_scope

pytestmark = pytest.mark.no_blockbuster


async def test_metrics_separate_source_replay_test_and_hint_events(make_trigger, owned_flow):
    from langflow.services.triggers.metrics import query_trigger_metrics

    trigger_id = await make_trigger()
    now = datetime.now(timezone.utc)
    job_id = uuid4()
    async with session_scope() as session:
        session.add(Job(job_id=job_id, flow_id=owned_flow, status=JobStatus.COMPLETED))
        session.add_all(
            [
                JobEvent(job_id=job_id, seq=0, event_type="run_started", created_at=now - timedelta(seconds=8)),
                JobEvent(job_id=job_id, seq=1, event_type="run_started", created_at=now - timedelta(seconds=4)),
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
    assert snapshot.oldest_pending_seconds == pytest.approx(90.0)


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
