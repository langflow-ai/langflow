"""Service-level contract tests for the ExecutorService."""

from __future__ import annotations

import pytest
from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete
from lfx.services.deps import get_service
from lfx.services.executor.service import ExecutorService
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType


def _get_service() -> ExecutorService:
    service = get_service(ServiceType.EXECUTOR_SERVICE)
    assert service is not None
    return service


def test_executor_service_is_resolvable_via_service_manager():
    service = _get_service()
    assert isinstance(service, ExecutorService)


def test_executor_service_preregisters_in_process():
    service = _get_service()
    assert service.has("in-process")
    assert service.get("in-process").kind == "in-process"


@pytest.mark.asyncio
async def test_coordinator_uses_settings_executor_kind():
    """Behavioral assertion: coordinator dispatches to whichever kind the settings select."""
    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    settings_service.settings.executor_kind = "kind-from-settings"

    seen: list[str] = []

    class Sentinel(Executor):
        kind = "kind-from-settings"

        async def execute(self, unit):  # noqa: ARG002
            seen.append(self.kind)
            yield RunComplete(outputs=["ok"])

    get_service_manager().update(ServiceType.EXECUTOR_SERVICE)
    service = _get_service()
    service.register(Sentinel())

    outputs = await service.coordinator.run_to_completion(graph=object(), inputs=[])

    assert seen == ["kind-from-settings"]
    assert outputs == ["ok"]

    settings_service.settings.executor_kind = "in-process"
    get_service_manager().update(ServiceType.EXECUTOR_SERVICE)


def test_register_replaces_and_invalidates_cached_coordinator():
    service = _get_service()
    first = service.coordinator

    class Other(Executor):
        kind = "in-process"

        async def execute(self, unit):  # noqa: ARG002
            yield RunComplete(outputs=[])

    service.register(Other())
    assert service.coordinator is not first
    assert isinstance(service.get("in-process"), Other)


@pytest.mark.asyncio
async def test_teardown_preserves_builtin_in_process():
    """teardown() must leave the service usable: the built-in must still be registered.

    ServiceManager.teardown() does not evict the cached service instance, so any code
    that resolves the service after teardown (e.g. background tasks racing app shutdown)
    must still get a working coordinator.
    """
    service = _get_service()

    custom_kinds_before = service.has("in-process")
    assert custom_kinds_before

    await service.teardown()

    assert service.has("in-process")
    assert service.coordinator is not None  # rebuilds lazily over the fresh registry


def test_entry_point_cannot_replace_builtin_in_process(monkeypatch):
    """A package exposing an executor with kind="in-process" must not silently replace the built-in."""
    from lfx.execution.backends.in_process import InProcessExecutor
    from lfx.services.executor import service as service_module

    class Hijacker(Executor):
        kind = "in-process"

        async def execute(self, unit):  # noqa: ARG002
            yield RunComplete(outputs=[])

    class _FakeEntryPoint:
        name = "hijacker"

        def load(self):
            return Hijacker

    monkeypatch.setattr(
        service_module,
        "entry_points",
        lambda group: [_FakeEntryPoint()] if group == service_module.ENTRY_POINT_GROUP else [],
    )

    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    fresh = ExecutorService(settings_service=settings_service)

    assert isinstance(fresh.get("in-process"), InProcessExecutor)


def test_entry_point_with_unique_kind_is_registered(monkeypatch):
    """Entry points with non-colliding kinds are still loaded."""
    from lfx.services.executor import service as service_module

    class RemoteStub(Executor):
        kind = "remote-stub"

        async def execute(self, unit):  # noqa: ARG002
            yield RunComplete(outputs=[])

    class _FakeEntryPoint:
        name = "remote_stub"

        def load(self):
            return RemoteStub

    monkeypatch.setattr(
        service_module,
        "entry_points",
        lambda group: [_FakeEntryPoint()] if group == service_module.ENTRY_POINT_GROUP else [],
    )

    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    fresh = ExecutorService(settings_service=settings_service)

    assert fresh.has("remote-stub")
    assert isinstance(fresh.get("remote-stub"), RemoteStub)


def test_entry_point_load_failure_does_not_break_discovery(monkeypatch):
    """A single broken entry point must not prevent the built-in or other plugins from loading."""
    from lfx.execution.backends.in_process import InProcessExecutor
    from lfx.services.executor import service as service_module

    class GoodStub(Executor):
        kind = "good-stub"

        async def execute(self, unit):  # noqa: ARG002
            yield RunComplete(outputs=[])

    class _BrokenEntryPoint:
        name = "broken"

        def load(self):
            msg = "simulated import failure"
            raise ImportError(msg)

    class _GoodEntryPoint:
        name = "good_stub"

        def load(self):
            return GoodStub

    monkeypatch.setattr(
        service_module,
        "entry_points",
        lambda group: [_BrokenEntryPoint(), _GoodEntryPoint()] if group == service_module.ENTRY_POINT_GROUP else [],
    )

    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    fresh = ExecutorService(settings_service=settings_service)

    assert isinstance(fresh.get("in-process"), InProcessExecutor)
    assert isinstance(fresh.get("good-stub"), GoodStub)


def test_entry_point_returning_non_executor_is_skipped(monkeypatch):
    """An entry point whose loaded object lacks `kind` must not crash discovery."""
    from lfx.execution.backends.in_process import InProcessExecutor
    from lfx.services.executor import service as service_module

    class NotAnExecutor:
        pass

    class _BadEntryPoint:
        name = "bad"

        def load(self):
            return NotAnExecutor

    monkeypatch.setattr(
        service_module,
        "entry_points",
        lambda group: [_BadEntryPoint()] if group == service_module.ENTRY_POINT_GROUP else [],
    )

    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    fresh = ExecutorService(settings_service=settings_service)

    assert isinstance(fresh.get("in-process"), InProcessExecutor)


def test_factory_declares_settings_dependency():
    """Pin the factory contract: ExecutorService depends on settings_service only."""
    from lfx.services.executor.factory import ExecutorServiceFactory

    factory = ExecutorServiceFactory()
    assert factory.service_class is ExecutorService
    assert factory.dependencies == [ServiceType.SETTINGS_SERVICE]
