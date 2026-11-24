"""Job retention must not strand a trigger ledger row in DISPATCHED.

``reconcile_dispatched`` learns a dispatched run's outcome by joining its job.
The ledger has no foreign key to ``job`` on purpose, so the job is purged on its
own schedule; a purge that ran before reconciliation would leave the ledger row
DISPATCHED with nothing left to join, and nothing else ever closes it.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import get_job_service, session_scope
from langflow.services.triggers import dispatcher

pytestmark = pytest.mark.no_blockbuster


async def test_purge_waits_until_the_ledger_reconciles_a_dispatched_job(make_trigger):
    trigger_id = await make_trigger()
    aged = datetime.now(timezone.utc) - timedelta(days=90)
    job_id = uuid4()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        session.add(
            Job(
                job_id=job_id,
                flow_id=trigger.flow_id,
                user_id=trigger.user_id,
                status=JobStatus.COMPLETED,
                created_timestamp=aged,
                finished_timestamp=aged,
            )
        )
        event = TriggerEvent(trigger_id=trigger_id, dedupe_key="aged-run", state="dispatched", job_id=job_id)
        session.add(event)
        await session.flush()
        event_id = event.id
    job_service = get_job_service()

    await job_service.purge_terminal_jobs(older_than_days=30, limit=100)
    assert await job_service.get_job_by_job_id(job_id) is not None

    async with session_scope() as session:
        assert await dispatcher.reconcile_dispatched(session) == 1
    await job_service.purge_terminal_jobs(older_than_days=30, limit=100)

    assert await job_service.get_job_by_job_id(job_id) is None
    async with session_scope() as session:
        event = await session.get(TriggerEvent, event_id)
        assert event.state == "completed"
        assert event.job_id == job_id
