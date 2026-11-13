"""Trigger run diagnostics preserve provider guidance and execution ownership."""

from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from langflow.services.triggers.dispatcher import reconcile_dispatched
from lfx.schema.message import ErrorMessage

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


@pytest.mark.parametrize("kind", ["whatsapp.event", "discord.message", "discord.mention"])
@pytest.mark.parametrize("foreign_field", ["user_id", "flow_id"])
async def test_event_error_lookup_does_not_cross_job_owners_or_flows(
    client, logged_in_headers, flow, kind, foreign_field
):
    async with session_scope() as session:
        trigger = Trigger(flow_id=flow.id, user_id=flow.user_id, name="Trigger", kind=kind, state="active")
        session.add(trigger)
        await session.flush()
        job = Job(
            job_id=uuid4(),
            flow_id=uuid4() if foreign_field == "flow_id" else flow.id,
            user_id=uuid4() if foreign_field == "user_id" else flow.user_id,
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


@pytest.mark.parametrize(
    ("job_error", "expected"),
    [
        (
            {"error": "Error building Type Convert: Input is required."},
            "Error building Type Convert: Input is required.",
        ),
        (
            {"message": "Choose a valid conversion type.", "stack_trace": "private traceback"},
            "Choose a valid conversion type.",
        ),
        ({"error": {"message": "A component input is missing."}}, "A component input is missing."),
        (
            ErrorMessage(ValueError("Type Convert requires an input."), include_traceback=False).model_dump(
                mode="json"
            ),
            "Type Convert requires an input.",
        ),
        ({"stack_trace": "private traceback", "details": {"token": "private-provider-token"}}, None),
    ],
)
@pytest.mark.parametrize("kind", ["discord.message", "discord.mention"])
async def test_discord_owner_sees_the_failed_runs_primary_message(
    client, logged_in_headers, flow, job_error, expected, kind
):
    async with session_scope() as session:
        trigger = Trigger(flow_id=flow.id, user_id=flow.user_id, name="Discord", kind=kind, state="active")
        session.add(trigger)
        await session.flush()
        job = Job(job_id=uuid4(), flow_id=flow.id, user_id=flow.user_id, status=JobStatus.FAILED, error=job_error)
        session.add(job)
        session.add(
            TriggerEvent(trigger_id=trigger.id, dedupe_key="discord-failed", state="dispatched", job_id=job.job_id)
        )
        await session.flush()
        await reconcile_dispatched(session)
        trigger_id = trigger.id

    response = await client.get(f"api/v1/triggers/{trigger_id}/events", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    [event] = response.json()
    assert event["state"] == "failed"
    assert event["error"] == "job_failed"
    assert event["error_detail"] == expected
    assert "private traceback" not in response.text
    assert "private-provider-token" not in response.text


@pytest.mark.parametrize("kind", ["discord.message", "discord.mention"])
@pytest.mark.parametrize("reader", ["shared", "former_owner"])
async def test_discord_run_error_is_not_disclosed_to_a_shared_reader(
    client, logged_in_headers, active_user, monkeypatch, kind, reader
):
    from langflow.services.authorization import fetch, guards
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_settings_service

    async with session_scope() as session:
        owner = User(username=f"discord-owner-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(owner)
        await session.flush()
        shared_flow = Flow(name="Shared Discord flow", user_id=owner.id)
        session.add(shared_flow)
        await session.flush()
        execution_owner_id = active_user.id if reader == "former_owner" else owner.id
        trigger = Trigger(flow_id=shared_flow.id, user_id=execution_owner_id, name="Discord", kind=kind)
        session.add(trigger)
        await session.flush()
        job = Job(
            job_id=uuid4(),
            flow_id=shared_flow.id,
            user_id=execution_owner_id,
            status=JobStatus.FAILED,
            error={"error": "private-owner-diagnostics"},
        )
        session.add(job)
        session.add(
            TriggerEvent(
                trigger_id=trigger.id, dedupe_key="shared", state="failed", job_id=job.job_id, error="job_failed"
            )
        )
        await session.flush()
        trigger_id = trigger.id

    class ReadPermission:
        async def supports_cross_user_fetch(self):
            return True

        async def is_enabled(self):
            return True

        async def enforce(self, *, user_id, domain, obj, act, context):  # noqa: ARG002
            assert user_id == active_user.id
            return obj == f"flow:{shared_flow.id}" and act == "read"

    authz = ReadPermission()
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(fetch, "get_authorization_service", lambda: authz)
    monkeypatch.setattr(guards, "get_authorization_service", lambda: authz)

    response = await client.get(f"api/v1/triggers/{trigger_id}/events", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.json()[0]["error_detail"] is None
    assert "private-owner-diagnostics" not in response.text
