"""Push sources reconcile periodically even without an ingress delivery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, leases, ledger, source_runtime
from langflow.services.triggers.dispatcher import reconcile_push_sources
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx.integrations.errors import ConnectionUnresolvedError


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


@pytest.mark.parametrize("source_hints", [False, True], ids=["periodic", "hint"])
@pytest.mark.parametrize(
    "reason", ["credential-undecryptable", "registration-unavailable", "source-config", "provider", "value-error"]
)
async def test_reconciliation_error_preserves_only_safe_configuration_guidance(
    make_trigger, monkeypatch, source_hints, reason
) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        if source_hints:
            event, _ = await ledger.append_event(
                session, trigger_id=trigger_id, dedupe_key="source-failure", payload={"_source_hint": True}
            )
            event_id = event.id
        else:
            session.add(
                TriggerSubscription(
                    trigger_id=trigger_id,
                    provider="google",
                    provider_subscription_id=str(uuid4()),
                    state=TriggerSubscriptionState.ACTIVE.value,
                )
            )

    if reason == "provider":
        request = httpx.Request("GET", "https://provider.test/items?access_token=fixture-secret")
        failure = httpx.HTTPStatusError(
            "Provider rejected fixture-secret", request=request, response=httpx.Response(500, request=request)
        )
    elif reason == "value-error":
        failure = ValueError("Provider returned invalid fixture-secret")
    elif reason == "source-config":
        failure = SourceConfigurationError("All Gmail triggers for one mailbox must use the same Pub/Sub topic.")
    else:
        failure = ConnectionUnresolvedError("connection:google/fixture-secret", provider="google", reason=reason)

    async def unavailable(_identifier):
        raise failure

    monkeypatch.setattr(source_runtime, "sync_source", unavailable)
    if source_hints:
        await dispatcher.run_once(owner="source-failure", source_hints=True)
    else:
        assert await reconcile_push_sources() == 0
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "active"
        assert trigger.last_error.startswith("Source reconciliation failed:")
        assert "fixture-secret" not in trigger.last_error
        if reason in {"provider", "value-error"}:
            assert trigger.last_error == f"Source reconciliation failed: {type(failure).__name__}"
        elif reason == "source-config":
            assert "All Gmail triggers for one mailbox must use the same Pub/Sub topic" in trigger.last_error
        else:
            assert reason in trigger.last_error
            assert "LANGFLOW_SECRET_KEY" in trigger.last_error
            assert "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS" in trigger.last_error
        if source_hints:
            event = await session.get(TriggerEvent, event_id)
            assert event.state == "pending"
            assert event.error == f"expand_failed:{type(failure).__name__}"


@pytest.mark.parametrize("last_error", ["Source reconciliation failed: RuntimeError", "connection_not_authorized"])
async def test_successful_hint_reconciliation_clears_only_its_own_error(make_trigger, monkeypatch, last_error) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.last_error = last_error
        session.add(trigger)
        event, _ = await ledger.append_event(
            session, trigger_id=trigger_id, dedupe_key="source-recovered", payload={"_source_hint": True}
        )
        event_id = event.id

    async def poll(identifier) -> int:
        async with session_scope() as session:
            trigger = await session.get(Trigger, identifier)
            trigger.next_fire_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            session.add(trigger)
        return 0

    monkeypatch.setattr(source_runtime, "sync_source", poll)
    await dispatcher.run_once(owner="source-recovered", source_hints=True)
    async with session_scope() as session:
        assert (await session.get(TriggerEvent, event_id)).state == "completed"
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.last_error == (None if last_error.startswith("Source reconciliation failed:") else last_error)
        assert trigger.next_fire_at > datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.parametrize("source_hints", [False, True], ids=["periodic", "hint"])
@pytest.mark.parametrize("new_error", ["connection_not_authorized", "Source reconciliation failed: RateLimitedError"])
async def test_reconciliation_preserves_an_error_written_during_source_io(
    make_trigger, monkeypatch, source_hints, new_error
):
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.last_error = "Source reconciliation failed: RuntimeError"
        session.add(trigger)
        if source_hints:
            event, _ = await ledger.append_event(
                session, trigger_id=trigger_id, dedupe_key="concurrent-error", payload={"_source_hint": True}
            )
            event_id = event.id
        else:
            session.add(
                TriggerSubscription(
                    trigger_id=trigger_id,
                    provider="google",
                    provider_subscription_id=str(uuid4()),
                    state=TriggerSubscriptionState.ACTIVE.value,
                )
            )

    async def poll(identifier) -> int:
        async with session_scope() as session:
            trigger = await session.get(Trigger, identifier)
            trigger.last_error = new_error
            session.add(trigger)
        return 0

    async def provision(_identifier):
        return None

    monkeypatch.setattr(source_runtime, "sync_source", poll)
    monkeypatch.setattr(source_runtime, "ensure_subscription", provision)
    if source_hints:
        await dispatcher.run_once(owner="concurrent-error", source_hints=True)
    else:
        assert await reconcile_push_sources() == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).last_error == new_error
        if source_hints:
            assert (await session.get(TriggerEvent, event_id)).state == "completed"


@pytest.mark.parametrize("source_hints", [False, True], ids=["periodic", "hint"])
async def test_successful_reconciliation_preserves_a_newer_identical_error_after_lease_release(
    make_trigger, monkeypatch, source_hints
):
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    same_error = "Source reconciliation failed: HTTPStatusError"
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.last_error = same_error
        session.add(trigger)
        if source_hints:
            event, _ = await ledger.append_event(
                session, trigger_id=trigger_id, dedupe_key="newer-same-error", payload={"_source_hint": True}
            )
            event_id = event.id
        else:
            session.add(
                TriggerSubscription(
                    trigger_id=trigger_id,
                    provider="google",
                    provider_subscription_id=str(uuid4()),
                    state=TriggerSubscriptionState.ACTIVE.value,
                )
            )

    async def poll(_identifier) -> int:
        return 0

    async def provision(_identifier):
        return None

    real_reconcile = source_runtime.reconcile_source

    async def fail_after_recovery(identifier, *, repair_subscription=False):
        result = await real_reconcile(identifier, repair_subscription=repair_subscription)
        async with session_scope() as session:
            assert await leases.holder(session, name=f"trigger-source:{identifier}") is None
            trigger = await session.get(Trigger, identifier)
            trigger.last_error = same_error
            session.add(trigger)
        return result

    monkeypatch.setattr(source_runtime, "sync_source", poll)
    monkeypatch.setattr(source_runtime, "ensure_subscription", provision)
    monkeypatch.setattr(source_runtime, "reconcile_source", fail_after_recovery)
    if source_hints:
        await dispatcher.run_once(owner="newer-same-error", source_hints=True)
    else:
        assert await reconcile_push_sources() == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).last_error == same_error
        if source_hints:
            assert (await session.get(TriggerEvent, event_id)).state == "completed"
