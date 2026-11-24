"""The lease cadence settings have to agree with each other, not just be positive.

A connection lease is renewed inside the reconcile pass, so the longest a
healthy holder can go without renewing is a heartbeat that came due just after
one pass plus a whole reconcile interval. Three individually valid numbers can
combine to exceed the TTL, and the result is not a slow listener: it is a
replica whose adapter is still running while another one takes the connection
away from it. That is a startup error, not a runtime surprise.
"""

from __future__ import annotations

import pytest
from lfx.services.settings.base import Settings
from lfx.services.settings.groups.runtime import RuntimeSettings
from pydantic import ValidationError


def test_the_defaults_leave_room_to_renew() -> None:
    settings = RuntimeSettings()
    renewal_ceiling = settings.listener_heartbeat_interval_s + settings.listener_reconcile_interval_s
    assert renewal_ceiling < settings.listener_lease_ttl_s


@pytest.mark.parametrize(
    ("ttl", "heartbeat", "reconcile"),
    [
        # Each value is positive and individually sane; together they renew at 45s.
        (30.0, 25.0, 20.0),
        # Exactly equal is still wrong: the renewal lands as the lease expires.
        (30.0, 25.0, 5.0),
        # A heartbeat longer than the whole TTL.
        (30.0, 45.0, 1.0),
    ],
)
def test_a_cadence_that_can_expire_before_it_renews_is_rejected(ttl, heartbeat, reconcile) -> None:
    with pytest.raises(ValidationError, match="listener_lease_ttl_s"):
        RuntimeSettings(
            listener_lease_ttl_s=ttl,
            listener_heartbeat_interval_s=heartbeat,
            listener_reconcile_interval_s=reconcile,
        )


def test_a_longer_ttl_makes_a_slow_cadence_valid_again() -> None:
    settings = RuntimeSettings(
        listener_lease_ttl_s=120.0,
        listener_heartbeat_interval_s=25.0,
        listener_reconcile_interval_s=20.0,
    )
    assert settings.listener_lease_ttl_s == 120.0


def test_an_operator_who_sets_this_in_the_environment_is_stopped_at_startup(monkeypatch) -> None:
    """``Settings`` drops init kwargs and reads its own sources, so check that path too."""
    monkeypatch.setenv("LANGFLOW_LISTENER_HEARTBEAT_INTERVAL_S", "25")
    monkeypatch.setenv("LANGFLOW_LISTENER_RECONCILE_INTERVAL_S", "20")
    with pytest.raises(ValidationError, match="listener_lease_ttl_s"):
        Settings()
