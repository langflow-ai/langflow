"""The dispatcher's start/stop contract, as the API lifespan uses it."""

from __future__ import annotations

import pytest
from langflow.services.deps import session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.constants import DISPATCHER_LEASE_NAME
from langflow.services.triggers.dispatcher import TriggerDispatcher

pytestmark = pytest.mark.no_blockbuster


async def test_start_is_idempotent_and_stop_hands_the_lease_back(client) -> None:  # noqa: ARG001
    """A clean shutdown must not make the next replica wait out the TTL."""
    dispatcher = TriggerDispatcher(owner="lifecycle-owner")
    assert dispatcher.running is False

    dispatcher.start()
    first_task = dispatcher._task
    dispatcher.start()
    assert dispatcher._task is first_task
    assert dispatcher.running is True

    # Take the lease the way a live pass would, then shut down.
    async with session_scope() as session:
        await leases.acquire(session, name=DISPATCHER_LEASE_NAME, owner="lifecycle-owner", ttl_s=600)

    await dispatcher.stop()
    assert dispatcher.running is False

    async with session_scope() as session:
        assert await leases.holder(session, name=DISPATCHER_LEASE_NAME) is None
        assert await leases.acquire(session, name=DISPATCHER_LEASE_NAME, owner="next-replica", ttl_s=600)


async def test_stop_is_safe_before_start(client) -> None:  # noqa: ARG001
    """Startup can fail before the loop exists; shutdown still runs."""
    await TriggerDispatcher(owner="never-started").stop()
