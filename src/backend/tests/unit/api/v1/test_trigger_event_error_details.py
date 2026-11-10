"""Failed WhatsApp events expose fixed guidance instead of private job payloads."""

from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from langflow.services.triggers.dispatcher import reconcile_dispatched

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    ("job_error", "expected"),
    [
        (
            {"message": "Error building Reply. Use a WhatsApp inbound message event."},
            "Use a WhatsApp inbound message event.",
        ),
        (
            {"error": {"message": "Use the template language code, such as en_US or pt_BR."}},
            "Use the template language code, such as en_US or pt_BR.",
        ),
        ({"message": "private-provider-token arbitrary provider response"}, None),
        (
            {"message": ["Error building Reply. Use a WhatsApp inbound message event.", "private-provider-token"]},
            "Use a WhatsApp inbound message event.",
        ),
    ],
)
async def test_failed_event_returns_only_known_safe_guidance(client, logged_in_headers, flow, job_error, expected):
    async with session_scope() as session:
        trigger = Trigger(flow_id=flow.id, user_id=flow.user_id, name="WhatsApp", kind="whatsapp.event", state="active")
        session.add(trigger)
        await session.flush()
        job = Job(job_id=uuid4(), flow_id=flow.id, user_id=flow.user_id, status=JobStatus.FAILED, error=job_error)
        session.add(job)
        event = TriggerEvent(trigger_id=trigger.id, dedupe_key="failed-message", state="dispatched", job_id=job.job_id)
        session.add(event)
        await session.flush()
        await reconcile_dispatched(session)
        trigger_id = trigger.id
    response = await client.get(f"api/v1/triggers/{trigger_id}/events", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    [event] = response.json()
    assert event["error"] == "job_failed"
    assert event["error_detail"] == expected
    assert "private-provider-token" not in response.text


async def test_event_error_lookup_does_not_cross_job_owners(client, logged_in_headers, flow):
    async with session_scope() as session:
        trigger = Trigger(flow_id=flow.id, user_id=flow.user_id, name="WhatsApp", kind="whatsapp.event", state="active")
        session.add(trigger)
        await session.flush()
        job = Job(
            job_id=uuid4(),
            flow_id=flow.id,
            user_id=uuid4(),
            status=JobStatus.FAILED,
            error={"message": "Use a WhatsApp inbound message event."},
        )
        session.add(job)
        session.add(
            TriggerEvent(
                trigger_id=trigger.id, dedupe_key="foreign-job", state="failed", job_id=job.job_id, error="job_failed"
            )
        )
        await session.flush()
        trigger_id = trigger.id
    response = await client.get(f"api/v1/triggers/{trigger_id}/events", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()[0]["error_detail"] is None
