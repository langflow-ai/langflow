"""Non-expiring receivers can finish cleanup using an owned replacement."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import source_cleanup

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(params=["github", "gitlab", "whatsapp", "telegram"])
def provider(request):
    return request.param


async def pending_replacement(trigger_owner, owned_flow, provider, invalid=None):
    async with session_scope() as session:
        foreign = User(username=f"replacement-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(foreign)
        await session.flush()
        connection = Connection(
            provider_key="slack" if invalid == "connection_provider" else provider,
            name=f"replacement_{uuid4().hex}",
            display_name="Replacement",
            owner_id=None if invalid == "instance" else foreign.id if invalid == "connection_owner" else trigger_owner,
            ownership_mode="instance" if invalid == "instance" else "user",
            status="revoked" if invalid == "revoked" else "ready",
            allow_non_interactive=invalid != "background",
        )
        session.add(connection)
        await session.flush()
        trigger = Trigger(
            flow_id=owned_flow,
            user_id=foreign.id if invalid == "trigger_owner" else trigger_owner,
            name="Receiver",
            kind=f"{provider}.event",
            provider="slack" if invalid == "trigger_provider" else provider,
            connection_id=connection.id,
        )
        session.add(trigger)
        await session.flush()
        task = TriggerCleanup(
            id=uuid4(),
            trigger_id=trigger.id,
            user_id=trigger_owner,
            connection_id=None,
            provider=provider,
            kind="other.event" if invalid == "kind" else trigger.kind,
            provider_subscription_id="original-receiver",
            provider_state={"callback_url": "https://receiver.example/original"},
            available_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        if invalid == "retained_credential":
            task.encrypted_credential = "retained-credential-capability"
            task.credential_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        session.add(task)
        await session.flush()
        return task.id, connection.id


async def test_replacement_resumes_backed_off_cleanup(monkeypatch, trigger_owner, owned_flow, provider):
    task_id, connection_id = await pending_replacement(trigger_owner, owned_flow, provider)
    calls = []

    async def revoke(task):
        calls.append((task.id, task.provider, task.connection_id, task.provider_state))

    monkeypatch.setattr(source_cleanup, "_revoke", revoke)
    assert await source_cleanup.run_cleanup_pass() == 1
    assert calls == [(task_id, provider, connection_id, {"callback_url": "https://receiver.example/original"})]
    async with session_scope() as session:
        assert await session.get(TriggerCleanup, task_id) is None


@pytest.mark.parametrize(
    "invalid",
    [
        "connection_owner",
        "trigger_owner",
        "connection_provider",
        "trigger_provider",
        "kind",
        "background",
        "instance",
        "revoked",
        "retained_credential",
    ],
)
async def test_replacement_keeps_ownership_and_consent_guards(
    monkeypatch, trigger_owner, owned_flow, provider, invalid
):
    task_id, _connection_id = await pending_replacement(trigger_owner, owned_flow, provider, invalid)

    async def revoke(_task):
        pytest.fail("An unrelated replacement must not retry remote cleanup")

    monkeypatch.setattr(source_cleanup, "_revoke", revoke)
    assert await source_cleanup.run_cleanup_pass() == 0
    async with session_scope() as session:
        task = await session.get(TriggerCleanup, task_id)
        assert task is not None
        assert task.connection_id is None


async def test_unreviewed_provider_cannot_replace_cleanup_connection(monkeypatch, trigger_owner, owned_flow):
    task_id, _connection_id = await pending_replacement(trigger_owner, owned_flow, "custom_provider")

    async def revoke(_task):
        pytest.fail("An unreviewed adapter cannot receive replacement cleanup credentials")

    monkeypatch.setattr(source_cleanup, "_revoke", revoke)
    assert await source_cleanup.run_cleanup_pass() == 0
    async with session_scope() as session:
        task = await session.get(TriggerCleanup, task_id)
        assert task is not None
        assert task.connection_id is None
