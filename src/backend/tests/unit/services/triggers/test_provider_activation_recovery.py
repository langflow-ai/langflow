"""Shared push activation preserves live receivers and exposes abandoned setup."""

from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.deps import session_scope
from langflow.services.triggers import leases, source_runtime
from langflow.services.triggers.service import TriggerService
from sqlmodel import select

from tests.unit.services.triggers import test_provider_lifecycle as provider_tests

pytestmark = pytest.mark.no_blockbuster
pilot = provider_tests.pilot


async def test_enabling_an_unchanged_active_receiver_preserves_subscription(
    pilot, trigger_owner, owned_flow, monkeypatch
):
    await provider_tests._connection(trigger_owner)
    trigger = await provider_tests._reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).one()
        subscription_id = subscription.id
        public_id, secret = row.public_id, row.signing_secret_encrypted
    preparations, provisions = list(pilot.prepared), list(pilot.provisions)

    async def unavailable_provider(_trigger_id):
        pytest.fail("An unchanged active receiver must not contact the provider again")

    monkeypatch.setattr(source_runtime, "initialize_source", unavailable_provider)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert (row.public_id, row.signing_secret_encrypted) == (public_id, secret)
        subscription = await session.get(TriggerSubscription, subscription_id)
        assert subscription.state == "active"
    assert pilot.prepared == preparations
    assert pilot.provisions == provisions


@pytest.mark.parametrize("subscription_state", ["pending", "active"])
@pytest.mark.parametrize("live_initializer", [False, True])
async def test_only_abandoned_activation_becomes_retryable(
    pilot, trigger_owner, owned_flow, subscription_state, live_initializer
):
    await provider_tests._connection(trigger_owner)
    trigger = await provider_tests._reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).one()
        subscription.state = subscription_state
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session.add(subscription)
        session.add(row)
        if live_initializer:
            assert await leases.acquire(
                session, name=f"trigger-source:{row.id}", owner="live-provider-setup", ttl_s=3600
            )
    await source_runtime.mark_interrupted_activations()
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        if live_initializer:
            assert row.state == "pending"
            assert row.last_error is None
        else:
            assert row.state == "error"
            assert "Enable the trigger to retry" in row.last_error
    assert pilot.provisions == []


async def test_maintenance_leaves_a_saved_receiver_unarmed(pilot, trigger_owner, owned_flow):
    await provider_tests._connection(trigger_owner)
    trigger = await provider_tests._reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session.add(row)
    await source_runtime.mark_interrupted_activations()
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert row.state == "pending"
        assert row.last_error is None
    assert pilot.prepared == []
    assert pilot.provisions == []
