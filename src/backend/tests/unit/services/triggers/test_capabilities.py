"""What the server tells a client it may do with a trigger, and why not.

The triggers settings page and the node badge render ``allowed_actions``,
``blocked_actions`` and ``reason`` as given; they never re-derive permission
from ``state``. These tests pin that vocabulary so a change to it is a
deliberate contract change, not a side effect.

Pure function, no database: the inputs are a trigger row and what the caller
may do on the trigger's flow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerAction, TriggerReason
from langflow.services.triggers.capabilities import TriggerCaller, trigger_capabilities, trigger_reason
from langflow.services.triggers.reconciliation import NODE_REMOVED_ERROR, SOURCE_SETTINGS_CHANGED_ERROR

FULL = TriggerCaller(can_write=True, can_execute=True, owns_connection=True)
READER = TriggerCaller(can_write=False, can_execute=False, owns_connection=False)

A = TriggerAction
R = TriggerReason


def _row(state: str = "active", *, kind: str = "schedule", **fields) -> Trigger:
    return Trigger(
        flow_id=uuid4(),
        user_id=uuid4(),
        name="trigger",
        kind=kind,
        config={},
        provider_state={},
        state=state,
        concurrency_limit=1,
        max_attempts=5,
        **fields,
    )


def _slack(state: str, **fields) -> Trigger:
    return _row(state, kind="slack.message", provider="slack", connection_id=uuid4(), **fields)


def test_a_healthy_schedule_offers_pause_test_replay_and_delete() -> None:
    caps = trigger_capabilities(_row("active"), caller=FULL)

    assert caps.reason is None
    assert caps.allowed_actions == (A.PAUSE, A.TEST, A.REPLAY, A.DELETE)
    # Resume is not applicable to a running trigger, and a schedule has no
    # connection to reconnect and no secret to rotate, so none of them appear.
    assert caps.blocked_actions == {}


def test_a_paused_trigger_offers_resume_and_explains_why_test_is_off() -> None:
    """A test or replay on a paused trigger would be retired, never run."""
    caps = trigger_capabilities(_row("paused"), caller=FULL)

    assert caps.reason is R.PAUSED
    assert caps.allowed_actions == (A.RESUME, A.DELETE)
    assert caps.blocked_actions == {A.TEST: R.PAUSED, A.REPLAY: R.PAUSED}


def test_an_admin_pause_is_a_distinct_reason_the_owner_can_still_resume() -> None:
    caps = trigger_capabilities(_row("paused", admin_paused_at=datetime.now(timezone.utc)), caller=FULL)

    assert caps.reason is R.PAUSED_BY_ADMIN
    assert A.RESUME in caps.allowed_actions
    assert caps.blocked_actions == {A.TEST: R.PAUSED_BY_ADMIN, A.REPLAY: R.PAUSED_BY_ADMIN}


def test_a_stale_admin_marker_on_a_running_trigger_is_ignored() -> None:
    """The marker only explains a pause; it never outlives the pause it explains."""
    row = _row("active", admin_paused_at=datetime.now(timezone.utc))
    assert trigger_reason(row) is None


@pytest.mark.parametrize("state", ["active", "pending", "needs_reconnect", "error", "expired", "dead"])
def test_any_write_of_another_state_releases_the_admin_marker(state) -> None:
    """Enforced on the model: the dispatcher and listeners write ``state`` directly, not through the service."""
    row = _row("paused", admin_paused_at=datetime.now(timezone.utc))

    row.state = state

    assert row.admin_paused_at is None


def test_re_pausing_keeps_the_admin_marker() -> None:
    row = _row("paused", admin_paused_at=datetime.now(timezone.utc))
    row.state = "paused"
    assert row.admin_paused_at is not None


@pytest.mark.parametrize(
    ("state", "last_error", "expected"),
    [
        pytest.param("pending", None, R.PENDING, id="pending"),
        pytest.param("pending", "Cron expression is invalid", R.CONFIG_INVALID, id="pending-with-error"),
        pytest.param("active", None, None, id="active"),
        pytest.param("active", "listener could not connect", R.DEGRADED, id="active-with-error"),
        pytest.param("paused", None, R.PAUSED, id="paused"),
        pytest.param("paused", "Cron expression is invalid", R.PAUSED, id="paused-with-config-error"),
        pytest.param("paused", NODE_REMOVED_ERROR, R.NODE_REMOVED, id="node-removed"),
        pytest.param("paused", SOURCE_SETTINGS_CHANGED_ERROR, R.SOURCE_SETTINGS_CHANGED, id="source-changed"),
        pytest.param("error", "boom", R.ERROR, id="error"),
        pytest.param("needs_reconnect", "token revoked", R.NEEDS_RECONNECT, id="needs-reconnect"),
        pytest.param("needs_reconnect", "connection_not_authorized", R.CONSENT_REQUIRED, id="consent"),
        pytest.param("expired", None, R.EXPIRED, id="expired"),
        pytest.param("dead", "terminal failure", R.DEAD, id="dead"),
    ],
)
def test_every_state_maps_to_one_stable_reason(state, last_error, expected) -> None:
    assert trigger_reason(_row(state, last_error=last_error)) is expected


def test_missing_consent_routes_to_reconnect_not_an_oauth_loop() -> None:
    """``consent_required`` tells the UI to open the background-runs switch (B9)."""
    caps = trigger_capabilities(_slack("needs_reconnect", last_error="connection_not_authorized"), caller=FULL)

    assert caps.reason is R.CONSENT_REQUIRED
    assert A.RECONNECT in caps.allowed_actions
    # Resume stays offered: it is the step after consent is granted.
    assert A.RESUME in caps.allowed_actions


def test_only_the_connection_owner_may_reconnect() -> None:
    editor = TriggerCaller(can_write=True, can_execute=True, owns_connection=False)
    caps = trigger_capabilities(_slack("needs_reconnect", last_error="token revoked"), caller=editor)

    assert A.RECONNECT not in caps.allowed_actions
    assert caps.blocked_actions[A.RECONNECT] is R.NOT_CONNECTION_OWNER


def test_reconnect_on_a_healthy_provider_trigger_explains_itself() -> None:
    caps = trigger_capabilities(_slack("active"), caller=FULL)

    assert caps.blocked_actions[A.RECONNECT] is R.RECONNECT_NOT_NEEDED


def test_a_dead_trigger_can_only_be_deleted() -> None:
    caps = trigger_capabilities(_row("dead", last_error="terminal failure"), caller=FULL)

    assert caps.reason is R.DEAD
    assert caps.allowed_actions == (A.DELETE,)
    assert caps.blocked_actions == {A.RESUME: R.DEAD, A.TEST: R.DEAD, A.REPLAY: R.DEAD}


def test_only_inbound_webhooks_offer_secret_rotation() -> None:
    assert A.ROTATE_SECRET in trigger_capabilities(_row(kind="inbound_webhook"), caller=FULL).allowed_actions
    assert A.ROTATE_SECRET not in trigger_capabilities(_slack("active"), caller=FULL).allowed_actions


def test_a_reader_sees_every_control_blocked_by_permission() -> None:
    caps = trigger_capabilities(_row("active", kind="inbound_webhook"), caller=READER)

    assert caps.allowed_actions == ()
    assert caps.blocked_actions == {
        A.PAUSE: R.INSUFFICIENT_PERMISSION,
        A.TEST: R.INSUFFICIENT_PERMISSION,
        A.REPLAY: R.INSUFFICIENT_PERMISSION,
        A.DELETE: R.INSUFFICIENT_PERMISSION,
        A.ROTATE_SECRET: R.INSUFFICIENT_PERMISSION,
    }


def test_execute_without_write_runs_but_does_not_manage() -> None:
    runner = TriggerCaller(can_write=False, can_execute=True, owns_connection=False)
    caps = trigger_capabilities(_row("active"), caller=runner)

    assert caps.allowed_actions == (A.TEST, A.REPLAY)
    assert caps.blocked_actions == {A.PAUSE: R.INSUFFICIENT_PERMISSION, A.DELETE: R.INSUFFICIENT_PERMISSION}


def test_a_state_reason_wins_over_a_permission_reason() -> None:
    """A reader looking at a dead trigger learns it is dead, not that they lack access."""
    caps = trigger_capabilities(_row("dead"), caller=READER)

    assert caps.blocked_actions[A.TEST] is R.DEAD
    assert caps.blocked_actions[A.DELETE] is R.INSUFFICIENT_PERMISSION
