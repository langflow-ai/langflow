"""Subscription renewal: leased, ahead of expiry, and honest about lifecycle.

A push trigger stops firing silently when its subscription expires, so these
tests are about the failure nobody notices: nothing raises, nothing logs, the
trigger still says "active", and no event ever arrives again.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerState, TriggerSubscriptionState
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases, subscriptions
from langflow.services.triggers.constants import SUBSCRIPTION_LEASE_NAME
from langflow.services.triggers.ingress.verifiers import state_digest

pytestmark = pytest.mark.no_blockbuster

PROVIDER = "microsoft"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def make_connection(trigger_owner):
    async def _make(**overrides):
        fields = {
            "provider_key": "microsoft",
            "name": f"conn_{uuid4().hex[:6]}",
            "display_name": "Microsoft",
            "ownership_mode": "user",
            "owner_id": trigger_owner,
            "status": "ready",
            "allow_non_interactive": True,
        }
        fields.update(overrides)
        async with session_scope() as session:
            row = Connection(**fields)
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row.id

    return _make


@pytest.fixture
def make_subscription(make_trigger, make_connection):
    async def _make(*, lifetime: timedelta = timedelta(days=7), connection_id=None, **trigger_fields):
        connection_id = connection_id if connection_id is not None else await make_connection()
        trigger_id = await make_trigger(
            kind="microsoft.mail", provider=PROVIDER, connection_id=connection_id, **trigger_fields
        )
        async with session_scope() as session:
            row = await subscriptions.upsert_subscription(
                session,
                trigger_id=trigger_id,
                connection_id=connection_id,
                provider=PROVIDER,
                provider_subscription_id=f"sub-{uuid4().hex[:8]}",
                client_state_digest=state_digest("client-state"),
                expires_at=_now() + lifetime,
            )
            return trigger_id, connection_id, row.id, row.provider_subscription_id

    return _make


@pytest.fixture
def fake_renewer():
    """Register a renewer for the test provider and clean it up afterwards."""
    calls: list[str] = []

    async def _renew(_session, subscription):
        calls.append(subscription.provider_subscription_id)
        return _now() + timedelta(days=7)

    subscriptions.register_renewer(PROVIDER, _renew)
    try:
        yield calls
    finally:
        subscriptions.unregister_renewer(PROVIDER)


async def _subscription(subscription_id) -> TriggerSubscription:
    async with session_scope() as session:
        return await session.get(TriggerSubscription, subscription_id)


async def _trigger(trigger_id) -> Trigger:
    async with session_scope() as session:
        return await session.get(Trigger, trigger_id)


# --------------------------------------------------------------------------- #
# The renewal schedule
# --------------------------------------------------------------------------- #


def test_the_renewal_lead_follows_the_subscription_lifetime(client) -> None:  # noqa: ARG001
    """A day ahead for a seven-day Graph mail subscription, twelve hours for a one-day one."""
    settings = get_settings_service().settings
    created = _now()

    seven_day = subscriptions.renew_after_for(created_at=created, expires_at=created + timedelta(days=7))
    one_day = subscriptions.renew_after_for(created_at=created, expires_at=created + timedelta(days=1))
    thirty_day = subscriptions.renew_after_for(created_at=created, expires_at=created + timedelta(days=30))

    assert (created + timedelta(days=7) - seven_day).total_seconds() == pytest.approx(
        settings.trigger_subscription_renew_lead_cap_s
    )
    assert (created + timedelta(days=1) - one_day).total_seconds() == pytest.approx(timedelta(hours=12).total_seconds())
    # The cap keeps a thirty-day subscription from throwing away fourteen days.
    assert (created + timedelta(days=30) - thirty_day).total_seconds() == pytest.approx(
        settings.trigger_subscription_renew_lead_cap_s
    )


async def test_a_subscription_is_renewed_before_it_expires(make_subscription, fake_renewer) -> None:
    _trigger_id, _connection_id, subscription_id, provider_subscription_id = await make_subscription()

    # Bring the row due, as the clock would a day before expiry.
    async with session_scope() as session:
        row = await session.get(TriggerSubscription, subscription_id)
        row.renew_after = _now() - timedelta(minutes=1)
        session.add(row)

    renewed = await subscriptions.run_renewal_pass(owner="replica-a")

    assert renewed == 1
    assert fake_renewer == [provider_subscription_id]
    row = await _subscription(subscription_id)
    assert row.state == TriggerSubscriptionState.ACTIVE.value
    assert row.expires_at.replace(tzinfo=timezone.utc) > _now() + timedelta(days=6)
    # The lease is handed back so the next pass can claim it again.
    assert row.lease_owner is None


async def test_a_subscription_that_is_not_due_is_left_alone(make_subscription, fake_renewer) -> None:
    await make_subscription()
    assert await subscriptions.run_renewal_pass(owner="replica-a") == 0
    assert fake_renewer == []


async def test_only_one_replica_renews_in_a_given_pass(make_subscription, fake_renewer) -> None:
    """Two API replicas, one provider call: the lease is what makes that true."""
    _trigger_id, _connection_id, subscription_id, _external = await make_subscription()
    async with session_scope() as session:
        row = await session.get(TriggerSubscription, subscription_id)
        row.renew_after = _now() - timedelta(minutes=1)
        session.add(row)

    first = await subscriptions.run_renewal_pass(owner="replica-a")
    second = await subscriptions.run_renewal_pass(owner="replica-b")

    assert (first, second) == (1, 0)
    assert len(fake_renewer) == 1
    async with session_scope() as session:
        assert await leases.holder(session, name=SUBSCRIPTION_LEASE_NAME) == "replica-a"


async def test_a_provider_with_no_registered_renewer_is_not_marked_broken(make_subscription) -> None:
    """No bundle installed is not the same as renewal failed."""
    _trigger_id, _connection_id, subscription_id, _external = await make_subscription()
    async with session_scope() as session:
        row = await session.get(TriggerSubscription, subscription_id)
        row.renew_after = _now() - timedelta(minutes=1)
        session.add(row)

    assert await subscriptions.run_renewal_pass(owner="replica-a") == 0

    row = await _subscription(subscription_id)
    assert row.state == TriggerSubscriptionState.ACTIVE.value
    assert row.lease_owner is None


async def test_a_failing_renewal_stays_claimable_and_backs_off(make_subscription) -> None:
    """A transient provider error must not retire a subscription that still has time on it.

    Retiring it would do two things at once, both silent: ``claim_due`` only
    claims ACTIVE rows so it would never be retried, and intake only reads an
    ACTIVE row's digest so every still-valid delivery would start failing.
    """

    async def _boom(_session, _subscription):
        msg = "graph said no"
        raise RuntimeError(msg)

    subscriptions.register_renewer(PROVIDER, _boom)
    try:
        trigger_id, _connection_id, subscription_id, _external = await make_subscription()
        async with session_scope() as session:
            row = await session.get(TriggerSubscription, subscription_id)
            row.renew_after = _now() - timedelta(minutes=1)
            session.add(row)

        assert await subscriptions.run_renewal_pass(owner="replica-a") == 0
    finally:
        subscriptions.unregister_renewer(PROVIDER)

    row = await _subscription(subscription_id)
    assert row.state == TriggerSubscriptionState.ACTIVE.value, "a live subscription must stay renewable"
    assert row.lease_owner is None
    assert row.provider_state["renew_failures"] == 1
    # Pushed into the future by the backoff, so the next pass does not spin.
    assert row.renew_after.replace(tzinfo=timezone.utc) > _now()
    # One failure is not yet worth telling the owner about.
    assert (await _trigger(trigger_id)).last_error is None


async def test_a_transient_failure_is_retried_and_deliveries_keep_verifying(make_subscription) -> None:
    """Fail once, succeed next pass — and the digest stays readable throughout."""
    from langflow.services.triggers.ingress import intake

    calls: list[str] = []

    async def _flaky(_session, subscription):
        calls.append(subscription.provider_subscription_id)
        if len(calls) == 1:
            msg = "graph said no"
            raise RuntimeError(msg)
        return _now() + timedelta(days=7)

    subscriptions.register_renewer(PROVIDER, _flaky)
    try:
        trigger_id, _connection_id, subscription_id, _external = await make_subscription()
        async with session_scope() as session:
            row = await session.get(TriggerSubscription, subscription_id)
            row.renew_after = _now() - timedelta(minutes=1)
            session.add(row)

        assert await subscriptions.run_renewal_pass(owner="replica-a") == 0

        # Between the failure and the retry, a delivery must still verify: the
        # subscription has not expired, so its digest is still the right one.
        async with session_scope() as session:
            trigger = await session.get(Trigger, trigger_id)
            secrets = await intake._subscription_secrets(session, trigger)
        assert secrets.client_state_digest == state_digest("client-state")

        # Bring it due again, as the backoff would.
        async with session_scope() as session:
            row = await session.get(TriggerSubscription, subscription_id)
            row.renew_after = _now() - timedelta(minutes=1)
            session.add(row)
        assert await subscriptions.run_renewal_pass(owner="replica-a") == 1
    finally:
        subscriptions.unregister_renewer(PROVIDER)

    assert len(calls) == 2
    row = await _subscription(subscription_id)
    assert row.state == TriggerSubscriptionState.ACTIVE.value
    assert "renew_failures" not in row.provider_state, "a success must clear the failure history"


async def test_persistent_failures_surface_on_the_trigger_and_a_success_clears_it(make_subscription) -> None:
    from langflow.services.deps import get_settings_service

    threshold = get_settings_service().settings.trigger_subscription_failure_threshold
    succeed = False

    async def _flaky(_session, _subscription):
        if succeed:
            return _now() + timedelta(days=7)
        msg = "graph said no"
        raise RuntimeError(msg)

    subscriptions.register_renewer(PROVIDER, _flaky)
    try:
        trigger_id, _connection_id, subscription_id, _external = await make_subscription()
        for _ in range(threshold):
            async with session_scope() as session:
                row = await session.get(TriggerSubscription, subscription_id)
                row.renew_after = _now() - timedelta(minutes=1)
                session.add(row)
            await subscriptions.run_renewal_pass(owner="replica-a")

        failing = await _trigger(trigger_id)
        assert "could not be renewed" in (failing.last_error or "")
        # Still armed: a struggling provider is not an owner misconfiguration.
        assert failing.state == TriggerState.ACTIVE.value

        succeed = True
        async with session_scope() as session:
            row = await session.get(TriggerSubscription, subscription_id)
            row.renew_after = _now() - timedelta(minutes=1)
            session.add(row)
        assert await subscriptions.run_renewal_pass(owner="replica-a") == 1
    finally:
        subscriptions.unregister_renewer(PROVIDER)

    assert (await _trigger(trigger_id)).last_error is None


async def test_an_expired_subscription_stops_consuming_renewal_attempts(make_subscription) -> None:
    """Only expiry is terminal: there is nothing left to renew."""

    async def _boom(_session, _subscription):
        msg = "graph said no"
        raise RuntimeError(msg)

    subscriptions.register_renewer(PROVIDER, _boom)
    try:
        trigger_id, _connection_id, subscription_id, _external = await make_subscription()
        async with session_scope() as session:
            row = await session.get(TriggerSubscription, subscription_id)
            row.renew_after = _now() - timedelta(minutes=1)
            row.expires_at = _now() - timedelta(minutes=1)
            session.add(row)

        assert await subscriptions.run_renewal_pass(owner="replica-a") == 0
    finally:
        subscriptions.unregister_renewer(PROVIDER)

    row = await _subscription(subscription_id)
    assert row.state == TriggerSubscriptionState.ERROR.value
    assert row.renew_after is None
    assert "could not be renewed" in ((await _trigger(trigger_id)).last_error or "")


# --------------------------------------------------------------------------- #
# Lifecycle and revocation
# --------------------------------------------------------------------------- #


async def test_reauthorization_required_moves_the_trigger_to_needs_reconnect(make_subscription) -> None:
    trigger_id, _connection_id, _subscription_id, provider_subscription_id = await make_subscription()

    async with session_scope() as session:
        changed = await subscriptions.apply_lifecycle(
            session,
            subscription_id=provider_subscription_id,
            event=subscriptions.LIFECYCLE_REAUTHORIZATION_REQUIRED,
        )

    assert changed is True
    row = await _trigger(trigger_id)
    assert row.state == TriggerState.NEEDS_RECONNECT.value
    assert "re-authorized" in (row.last_error or "")


async def test_subscription_removed_retires_the_row_and_asks_for_a_reconnect(make_subscription) -> None:
    trigger_id, _connection_id, subscription_id, provider_subscription_id = await make_subscription()

    async with session_scope() as session:
        await subscriptions.apply_lifecycle(
            session, subscription_id=provider_subscription_id, event=subscriptions.LIFECYCLE_SUBSCRIPTION_REMOVED
        )

    assert (await _subscription(subscription_id)).state == TriggerSubscriptionState.EXPIRED.value
    assert (await _trigger(trigger_id)).state == TriggerState.NEEDS_RECONNECT.value


async def test_a_missed_notification_is_recorded_without_disarming_the_trigger(make_subscription) -> None:
    """'missed' is a resync hint, not a reason to stop a working subscription."""
    trigger_id, _connection_id, subscription_id, provider_subscription_id = await make_subscription()

    async with session_scope() as session:
        await subscriptions.apply_lifecycle(
            session, subscription_id=provider_subscription_id, event=subscriptions.LIFECYCLE_MISSED
        )

    assert "missed_at" in (await _subscription(subscription_id)).provider_state
    assert (await _trigger(trigger_id)).state == TriggerState.ACTIVE.value


async def test_revoking_a_connection_retires_its_subscriptions(make_subscription, make_connection) -> None:
    connection_id = await make_connection()
    trigger_id, _connection_id, subscription_id, _external = await make_subscription(connection_id=connection_id)

    async with session_scope() as session:
        connection = await session.get(Connection, connection_id)
        connection.status = "revoked"
        session.add(connection)

    async with session_scope() as session:
        retired = await subscriptions.revoke_unusable_connections(session)

    assert retired == 1
    assert (await _subscription(subscription_id)).state == TriggerSubscriptionState.EXPIRED.value
    assert (await _trigger(trigger_id)).state == TriggerState.NEEDS_RECONNECT.value


async def test_disabling_a_trigger_retires_its_subscription(make_subscription) -> None:
    """A paused trigger with a live subscription keeps costing the provider's quota."""
    from langflow.services.deps import get_trigger_service

    trigger_id, _connection_id, subscription_id, _external = await make_subscription()

    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        await get_trigger_service().disable(session, row=row)

    assert (await _subscription(subscription_id)).state == TriggerSubscriptionState.EXPIRED.value
    assert (await _trigger(trigger_id)).state == TriggerState.PAUSED.value


async def test_a_retired_subscription_is_never_renewed_again(make_subscription, fake_renewer) -> None:
    trigger_id, _connection_id, subscription_id, _external = await make_subscription()
    async with session_scope() as session:
        await subscriptions.revoke_for_trigger(session, trigger_id=trigger_id)
        row = await session.get(TriggerSubscription, subscription_id)
        # Even if something put a due time back on it.
        row.renew_after = _now() - timedelta(minutes=1)
        session.add(row)

    assert await subscriptions.run_renewal_pass(owner="replica-a") == 0
    assert fake_renewer == []


# --------------------------------------------------------------------------- #
# Which subscription intake verifies against
# --------------------------------------------------------------------------- #


async def test_intake_reads_the_newest_active_subscription_not_a_retired_one(make_subscription) -> None:
    """Re-subscribing leaves the old row EXPIRED beside the new one.

    Handing back the retired row's digest would reject every valid notification
    as bad_client_state while the trigger still reported itself healthy.
    """
    from langflow.services.triggers.ingress import intake

    trigger_id, connection_id, old_subscription_id, _external = await make_subscription()

    async with session_scope() as session:
        # Retire the first subscription, then subscribe again with a new secret.
        await subscriptions.revoke_for_trigger(session, trigger_id=trigger_id)
        await subscriptions.upsert_subscription(
            session,
            trigger_id=trigger_id,
            connection_id=connection_id,
            provider=PROVIDER,
            provider_subscription_id=f"sub-{uuid4().hex[:8]}",
            client_state_digest=state_digest("new-client-state"),
            expires_at=_now() + timedelta(days=7),
        )

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        secrets = await intake._subscription_secrets(session, trigger)

    assert secrets.client_state_digest == state_digest("new-client-state")
    assert (await _subscription(old_subscription_id)).state == TriggerSubscriptionState.EXPIRED.value


async def test_no_active_subscription_yields_no_secret_rather_than_a_stale_one(make_subscription) -> None:
    from langflow.services.triggers.ingress import intake

    trigger_id, _connection_id, _subscription_id, _external = await make_subscription()
    async with session_scope() as session:
        await subscriptions.revoke_for_trigger(session, trigger_id=trigger_id)

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        secrets = await intake._subscription_secrets(session, trigger)

    assert secrets.client_state_digest is None


async def test_a_registered_revoker_is_called_before_the_row_is_retired(make_subscription) -> None:
    """TRG-6 registers the provider call; TRG-4 owns when it happens."""
    called: list[str] = []

    async def _revoke(_session, subscription):
        called.append(subscription.provider_subscription_id)

    subscriptions.register_revoker(PROVIDER, _revoke)
    try:
        trigger_id, _connection_id, _subscription_id, provider_subscription_id = await make_subscription()
        async with session_scope() as session:
            await subscriptions.revoke_for_trigger(session, trigger_id=trigger_id)
    finally:
        subscriptions.unregister_revoker(PROVIDER)

    assert called == [provider_subscription_id]


async def test_a_failing_revoker_still_retires_the_local_row(make_subscription) -> None:
    """The owner's pause must not depend on the provider answering."""

    async def _boom(_session, _subscription):
        msg = "graph said no"
        raise RuntimeError(msg)

    subscriptions.register_revoker(PROVIDER, _boom)
    try:
        trigger_id, _connection_id, subscription_id, _external = await make_subscription()
        async with session_scope() as session:
            assert await subscriptions.revoke_for_trigger(session, trigger_id=trigger_id) == 1
    finally:
        subscriptions.unregister_revoker(PROVIDER)

    assert (await _subscription(subscription_id)).state == TriggerSubscriptionState.EXPIRED.value


async def test_removing_the_canvas_node_retires_the_subscription_too(make_subscription) -> None:
    """Removing the node is as much an 'off' as pressing pause."""
    from langflow.services.triggers.reconciliation import reconcile_flow_triggers

    trigger_id, _connection_id, subscription_id, _external = await make_subscription()
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.node_id = "MicrosoftMailTrigger-abc12"
        session.add(trigger)
        flow_id, owner_id = trigger.flow_id, trigger.user_id

    # Save the flow with the trigger node gone.
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": [], "edges": []})

    assert (await _trigger(trigger_id)).state == TriggerState.PAUSED.value
    assert (await _subscription(subscription_id)).state == TriggerSubscriptionState.EXPIRED.value
