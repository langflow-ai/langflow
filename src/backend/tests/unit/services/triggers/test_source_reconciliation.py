"""Push sources reconcile periodically even without an ingress delivery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.deps import session_scope
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.dispatcher import reconcile_push_sources


async def test_due_push_source_is_scanned_without_a_hint(make_trigger, monkeypatch) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                provider="google",
                provider_subscription_id=str(uuid4()),
                state=TriggerSubscriptionState.ACTIVE.value,
            )
        )

    calls = []

    async def poll(_session, trigger: Trigger, *, family: str) -> int:
        calls.append((trigger.id, family))
        trigger.next_fire_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        _session.add(trigger)
        return 0

    monkeypatch.setattr("langflow.services.triggers.source_poll.poll_source", poll)
    assert await reconcile_push_sources() == 1
    assert calls == [(trigger_id, FAMILY_TRIGGER_PUSH)]
    assert await reconcile_push_sources() == 0
