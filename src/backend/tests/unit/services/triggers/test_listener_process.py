"""The process boundary, the packaging shapes, and the self-test adapter.

``decisions/process-model.md`` makes "the listener process hosts no API" a
decision rather than a convention. These tests are the enforcement: the flag,
the ``create_app`` refusal, the single-worker election for subprocess mode, and
the child command that Desktop and a single container rely on.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.constants import (
    LISTENER_FAKE_DEDUPE_PREFIX,
    LISTENER_FAKE_KIND,
    LISTENER_HOST_LEASE_NAME,
)
from langflow.services.triggers.listeners import guard
from langflow.services.triggers.listeners.adapters import (
    ListenerContext,
    ListenerTrigger,
    SelfTestAdapter,
    build_adapter,
    register_builtin_adapters,
)
from langflow.services.triggers.listeners.subprocess_host import (
    ListenerSubprocess,
    listener_command,
    start_listener_subprocess_if_enabled,
)

pytestmark = pytest.mark.no_blockbuster


# --------------------------------------------------------------------------- #
# The process boundary
# --------------------------------------------------------------------------- #


def test_a_listener_process_refuses_to_build_the_api(monkeypatch) -> None:
    """Both precedents ran the listener inside the API. This makes that an error."""
    from langflow import main as langflow_main

    monkeypatch.setattr(guard, "_IS_LISTENER_PROCESS", True)
    with pytest.raises(RuntimeError, match="must not host the API"):
        langflow_main.create_app()


def test_the_flag_is_off_in_an_ordinary_process() -> None:
    assert guard.is_listener_process() is False


def test_assert_no_http_app_rejects_a_process_that_already_built_one(monkeypatch) -> None:
    import sys as sys_module

    module = sys_module.modules.get("langflow.main")
    assert module is not None, "langflow.main is imported by the test suite"
    monkeypatch.setattr(module, "app", object(), raising=False)
    with pytest.raises(RuntimeError, match="must not host the API"):
        guard.assert_no_http_app()


def test_the_child_is_this_interpreter_not_a_path_lookup() -> None:
    """Desktop bundles a runtime with no console script on PATH."""
    command = listener_command()
    assert command[0] == sys.executable
    assert list(command[1:]) == ["-m", "langflow", "listeners"]


def test_the_listeners_command_is_registered_on_the_cli() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "langflow", "listeners", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert "listener" in result.stdout.lower()


# --------------------------------------------------------------------------- #
# Subprocess mode and its single-worker guard
# --------------------------------------------------------------------------- #


async def test_subprocess_mode_is_off_by_default(client) -> None:  # noqa: ARG001
    assert get_settings_service().settings.listeners_mode == "off"
    assert start_listener_subprocess_if_enabled() is None


async def test_exactly_one_api_worker_spawns_the_child(client, monkeypatch) -> None:  # noqa: ARG001
    """The API defaults to several workers; N listeners would fight over every lease."""
    spawned: list[str] = []

    def record(self) -> None:
        spawned.append(self.owner)

    monkeypatch.setattr(ListenerSubprocess, "spawn_child", record)

    worker_a = ListenerSubprocess(owner="worker-a")
    worker_b = ListenerSubprocess(owner="worker-b")

    assert await worker_a.tick() is True
    assert await worker_b.tick() is False

    assert spawned == ["worker-a"]
    async with session_scope() as session:
        assert await leases.holder(session, name=LISTENER_HOST_LEASE_NAME) == "worker-a"

    await worker_a.stop()
    await worker_b.stop()


async def test_a_worker_that_loses_the_host_lease_stands_down(client, monkeypatch) -> None:  # noqa: ARG001
    terminated: list[str] = []

    monkeypatch.setattr(ListenerSubprocess, "spawn_child", lambda _self: None)

    async def record_terminate(self) -> None:
        terminated.append(self.owner)

    monkeypatch.setattr(ListenerSubprocess, "terminate_child", record_terminate)

    worker = ListenerSubprocess(owner="worker-a")
    assert await worker.tick() is True

    # Another worker takes the lease while this one was busy.
    async with session_scope() as session:
        await leases.release(session, name=LISTENER_HOST_LEASE_NAME, owner="worker-a")
        await leases.acquire(session, name=LISTENER_HOST_LEASE_NAME, owner="worker-b", ttl_s=300)

    assert await worker.tick() is False
    assert terminated == ["worker-a"]
    await worker.stop()


# --------------------------------------------------------------------------- #
# The self-test adapter: the smoke test every packaging shape runs
# --------------------------------------------------------------------------- #


def _trigger(**overrides) -> ListenerTrigger:
    fields = {
        "id": uuid4(),
        "flow_id": uuid4(),
        "user_id": uuid4(),
        "kind": LISTENER_FAKE_KIND,
        "provider": None,
        "mechanism_id": None,
        "config": {},
        "provider_state": {},
    }
    fields.update(overrides)
    return ListenerTrigger(**fields)


async def test_the_self_test_adapter_is_registered_for_its_kind(client) -> None:  # noqa: ARG001
    register_builtin_adapters()
    adapter = build_adapter(_trigger())
    assert isinstance(adapter, SelfTestAdapter)


async def test_an_unregistered_kind_gets_no_adapter(client) -> None:  # noqa: ARG001
    register_builtin_adapters()
    assert build_adapter(_trigger(kind="schedule")) is None


async def test_the_self_test_dedupe_key_is_the_interval_bucket_not_the_clock(client) -> None:  # noqa: ARG001
    """A restart inside one bucket re-emits the same key, and the ledger keeps one."""
    trigger = _trigger()
    emitted: list[str] = []

    async def emit(*, trigger_id, dedupe_key, payload) -> bool:  # noqa: ARG001
        first = dedupe_key not in emitted
        emitted.append(dedupe_key)
        return first

    ctx = ListenerContext(
        connection_id=uuid4(),
        triggers=[trigger],
        emit=emit,
        save_cursor=None,
        resolve_credential=None,
        stopping=asyncio.Event(),
    )
    adapter = SelfTestAdapter(interval_s=3600)
    assert await adapter.poll(ctx) == 1
    assert await adapter.poll(ctx) == 0, "the second poll in the same bucket must be a duplicate"
    assert len(set(emitted)) == 1
    bucket = int(datetime.now(timezone.utc).timestamp() // 3600)
    assert emitted[0] == f"{LISTENER_FAKE_DEDUPE_PREFIX}:{bucket}"


async def test_the_poll_loop_stops_on_the_stopping_event(client) -> None:  # noqa: ARG001
    class CountingAdapter(SelfTestAdapter):
        def __init__(self) -> None:
            super().__init__(interval_s=0.01)
            self.polls = 0

        async def poll(self, ctx: ListenerContext) -> int:
            self.polls += 1
            if self.polls >= 3:
                ctx.stopping.set()
            return 0

    adapter = CountingAdapter()
    ctx = ListenerContext(
        connection_id=uuid4(),
        triggers=[_trigger()],
        emit=None,
        save_cursor=None,
        resolve_credential=None,
        stopping=asyncio.Event(),
    )
    await asyncio.wait_for(adapter.start(ctx), timeout=5)
    assert adapter.polls == 3


async def test_a_listener_resolves_its_own_connection_without_the_api(client, trigger_owner, make_trigger) -> None:  # noqa: ARG001
    """The 1.13 boundary obligation: INT-2's resolver is callable from this process.

    The listener never reaches the API over HTTP. It resolves - and refreshes -
    through the registered resolver service in its own process, which is the
    reason the sidecar design is possible at all.
    """
    from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

    async with session_scope() as session:
        connection = Connection(
            provider_key="selftest",
            name=f"conn_{uuid4().hex[:6]}",
            display_name="Self test",
            ownership_mode="user",
            owner_id=trigger_owner,
            status="ready",
            allow_non_interactive=True,
        )
        session.add(connection)
        await session.flush()
        connection_id = connection.id

    trigger_id = await make_trigger(kind=LISTENER_FAKE_KIND, connection_id=connection_id)
    register_builtin_adapters()

    supervisor = ListenerSupervisor(holder="replica-a")
    await supervisor.reconcile()
    try:
        assert connection_id in supervisor.workers
        ctx = supervisor._context(supervisor.workers[connection_id])
        # No provider credential exists for "selftest", so resolution must fail
        # with the resolver's own typed error - which proves the resolver ran
        # here, in this process, rather than a transport error from an API call.
        from lfx.integrations.errors import IntegrationError

        with pytest.raises(IntegrationError):
            await ctx.resolve_credential(trigger_id)
    finally:
        await supervisor.stop()
