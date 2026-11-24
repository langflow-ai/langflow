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


async def test_the_lifespan_helper_honours_the_setting(client, monkeypatch) -> None:  # noqa: ARG001
    """The wiring the API lifespan calls, exercised without booting a lifespan.

    The backend test app runs with ``LANGFLOW_TRIGGER_DISPATCHER_ENABLED=false``
    (a polling loop would race every test that drives the dispatcher directly),
    so the enabled branch is only ever reached here.
    """
    from langflow.services.deps import get_settings_service
    from langflow.services.triggers.dispatcher import start_dispatcher_if_enabled

    settings = get_settings_service().settings
    assert settings.trigger_dispatcher_enabled is False
    assert start_dispatcher_if_enabled() is None

    monkeypatch.setattr(settings, "trigger_dispatcher_enabled", True)
    dispatcher = start_dispatcher_if_enabled()
    assert dispatcher is not None
    assert dispatcher.running is True
    await dispatcher.stop()
    assert dispatcher.running is False


async def test_the_lifespan_helper_never_raises(client, monkeypatch) -> None:  # noqa: ARG001
    """A trigger loop that cannot start must not stop the API from booting."""
    from langflow.services.triggers import dispatcher as dispatcher_module

    settings = dispatcher_module.get_settings_service().settings
    monkeypatch.setattr(settings, "trigger_dispatcher_enabled", True)

    def _explode(*_args, **_kwargs):
        msg = "no event loop, no lease, no luck"
        raise RuntimeError(msg)

    monkeypatch.setattr(dispatcher_module, "TriggerDispatcher", _explode)
    assert dispatcher_module.start_dispatcher_if_enabled() is None
