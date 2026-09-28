"""Push sources reconcile periodically even without an ingress delivery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.deps import session_scope
from langflow.services.triggers.dispatcher import reconcile_push_sources


async def test_due_push_source_is_scanned_without_a_hint(make_trigger, monkeypatch) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.last_error = "Source reconciliation failed: RateLimitedError"
        session.add(trigger)
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                provider="google",
                provider_subscription_id=str(uuid4()),
                state=TriggerSubscriptionState.ACTIVE.value,
            )
        )

    calls = []

    async def poll(identifier) -> int:
        calls.append(identifier)
        async with session_scope() as session:
            trigger = await session.get(Trigger, identifier)
            trigger.next_fire_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            session.add(trigger)
        return 0

    async def provision(identifier):
        assert identifier == trigger_id

    monkeypatch.setattr("langflow.services.triggers.source_runtime.sync_source", poll)
    monkeypatch.setattr("langflow.services.triggers.source_runtime.ensure_subscription", provision)
    assert await reconcile_push_sources() == 1
    assert calls == [trigger_id]
    assert await reconcile_push_sources() == 0
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).last_error is None
