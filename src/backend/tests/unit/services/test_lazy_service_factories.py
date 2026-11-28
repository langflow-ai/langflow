"""Lazy fallback resolution preserves the manager's ownership and precedence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from langflow.services import deps
from langflow.services.base import Service
from lfx.services import manager as manager_module
from lfx.services.manager import NoFactoryRegisteredError, ServiceManager
from lfx.services.schema import ServiceType


class SessionService(Service):
    """Small service with the real readiness lifecycle."""

    name = ServiceType.SESSION_SERVICE


class CountingFactory:
    """Factory with observable construction, creation, and explicit dependencies."""

    service_class = SessionService
    dependencies = ()
    constructions = 0
    creations = 0

    def __init__(self):
        type(self).constructions += 1

    def create(self, **_kwargs):
        """Create a fresh managed service."""
        type(self).creations += 1
        return self.service_class()


@pytest.fixture
def manager(monkeypatch, tmp_path):
    """Isolate registrations and config without discovering installed plugins."""
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    instance = ServiceManager()
    instance._plugins_discovered = True
    instance.set_factory_registered()
    monkeypatch.setattr(manager_module, "get_service_manager", lambda: instance)
    monkeypatch.setattr(CountingFactory, "constructions", 0)
    monkeypatch.setattr(CountingFactory, "creations", 0)
    return instance


def unused_factory():
    """Fail if a fallback is touched when another source already owns the service."""
    message = "unused fallback was constructed"
    raise AssertionError(message)


def test_warm_lookup_and_registered_factory_do_not_construct_fallback(manager):
    """A fallback is constructed once, then the manager reuses its instance/factory."""
    first = manager.get(ServiceType.SESSION_SERVICE, default_factory=CountingFactory)
    for _ in range(10):
        assert manager.get(ServiceType.SESSION_SERVICE, default_factory=unused_factory) is first
    manager.services.pop(ServiceType.SESSION_SERVICE)
    second = manager.get(ServiceType.SESSION_SERVICE, default_factory=unused_factory)
    assert second is not first
    assert first.ready
    assert second.ready
    assert CountingFactory.constructions == 1
    assert CountingFactory.creations == 2


def test_registered_factory_and_legacy_instance_precede_provider(manager):
    """Both established factory-instance entry points retain their precedence."""
    factory = CountingFactory()
    first = manager.get(ServiceType.SESSION_SERVICE, factory, default_factory=unused_factory)
    assert first.ready
    manager.services.clear()
    manager.register_factory(factory)
    assert manager.get(ServiceType.SESSION_SERVICE, default_factory=unused_factory) is not first


def test_plugin_discovery_precedes_lazy_provider(manager, monkeypatch):
    """A plugin discovered on a cold lookup wins without evaluating the fallback."""
    manager._plugins_discovered = False

    def discover(_config):
        """Publish a plugin through the existing discovery boundary."""
        manager.register_service_class(ServiceType.SESSION_SERVICE, SessionService)
        manager._plugins_discovered = True

    monkeypatch.setattr(manager, "discover_plugins", discover)
    assert isinstance(manager.get(ServiceType.SESSION_SERVICE, default_factory=unused_factory), SessionService)


def test_settings_ignore_fallback_and_keep_builtin_factory(manager, monkeypatch):
    """Settings creation keeps its special built-in factory path."""
    from lfx.services.settings.factory import SettingsServiceFactory

    expected = SessionService()
    monkeypatch.setattr(SettingsServiceFactory, "create", lambda _self: expected)
    assert manager.get(ServiceType.SETTINGS_SERVICE, default_factory=unused_factory) is expected
    assert expected.ready


def test_concurrent_same_service_misses_construct_once(manager):
    """Concurrent first requests share the keyed lock, fallback, and managed result."""
    start = Barrier(8)

    def lookup(_index):
        """Synchronize cold callers before entering the existing keyed lock."""
        start.wait(timeout=10)
        return manager.get(ServiceType.SESSION_SERVICE, default_factory=CountingFactory)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lookup, range(8)))
    assert all(service is results[0] for service in results)
    assert CountingFactory.constructions == CountingFactory.creations == 1


def test_provider_failure_does_not_register_or_publish_and_can_retry(manager):
    """Constructor failure leaves the requested service absent and releases its lock."""
    with pytest.raises(AssertionError, match="unused fallback"):
        manager.get(ServiceType.SESSION_SERVICE, default_factory=unused_factory)
    assert ServiceType.SESSION_SERVICE not in manager.factories
    assert ServiceType.SESSION_SERVICE not in manager.services
    assert manager.get(ServiceType.SESSION_SERVICE, default_factory=CountingFactory).ready


def test_missing_dependency_does_not_publish_service(manager):
    """The existing missing-dependency error still leaves no managed result."""

    class DependentFactory(CountingFactory):
        dependencies = (ServiceType.DATABASE_SERVICE,)

    with pytest.raises(NoFactoryRegisteredError):
        manager.get(ServiceType.SESSION_SERVICE, default_factory=DependentFactory)
    assert ServiceType.SESSION_SERVICE not in manager.services


async def test_teardown_and_registration_override_recreate_in_same_manager(manager):
    """Teardown and explicit replacement do not leave a second service cache behind."""
    first = manager.get(ServiceType.SESSION_SERVICE, default_factory=CountingFactory)
    await manager.teardown()
    second = manager.get(ServiceType.SESSION_SERVICE, default_factory=CountingFactory)
    assert second is not first
    assert CountingFactory.constructions == 2
    manager.register_service_class(ServiceType.SESSION_SERVICE, SessionService)
    manager.update(ServiceType.SESSION_SERVICE)
    assert manager.services[ServiceType.SESSION_SERVICE] is not second


def test_real_backend_getter_skips_factory_construction_and_inference(manager, monkeypatch):
    """The state getter forwards a provider rather than constructing a discarded factory."""
    from langflow.services import factory as factory_module
    from langflow.services.state.factory import StateServiceFactory
    from langflow.services.state.service import InMemoryStateService

    expected = object()
    manager.services[ServiceType.STATE_SERVICE] = expected
    monkeypatch.setattr(StateServiceFactory, "__init__", lambda _self: unused_factory())
    monkeypatch.setattr(factory_module, "infer_service_types", unused_factory)
    assert deps.get_state_service() is expected
    assert InMemoryStateService.name == ServiceType.STATE_SERVICE


async def test_authenticated_run_preserves_response_with_less_factory_work(
    client, created_api_key, json_memory_chatbot_no_llm, monkeypatch
):
    """Compare authenticated/persisted ASGI runs with eager and lazy helper fallbacks.

    Set LANGFLOW_FACTORY_BENCHMARK_PAIRS for longer interleaved measurement runs;
    times are observations only. Constructor counts and normalized responses
    are the deterministic regression checks.
    """
    import json
    import os
    from time import perf_counter
    from uuid import uuid4

    from langflow.services import factory as factory_module
    from langflow.services.database.models.flow.model import Flow

    flow_id = uuid4()
    raw = json.loads(json_memory_chatbot_no_llm)
    async with deps.session_scope() as session:
        session.add(
            Flow(id=flow_id, name="Factory lookup parity", data=raw.get("data", raw), user_id=created_api_key.user_id)
        )
    resolve = deps.get_service
    initialize = factory_module.ServiceFactory.__init__
    infer = factory_module.infer_service_types
    counts = {"constructors": 0, "inference": 0}

    def counted_init(self, *args, **kwargs):
        """Count real backend factory construction, retaining its dependency inference."""
        counts["constructors"] += 1
        initialize(self, *args, **kwargs)

    def counted_infer(*args, **kwargs):
        """Count inference entry, including cached-key work."""
        counts["inference"] += 1
        return infer(*args, **kwargs)

    def eager(service_type, default=None, *, default_factory=None):
        """Reproduce the old helpers' eager construction before manager lookup."""
        if default_factory is not None:
            default = default_factory()
        return resolve(service_type, default)

    volatile = {
        "id",
        "session_id",
        "run_id",
        "graph_run_id",
        "timestamp",
        "created_at",
        "updated_at",
        "duration",
        "elapsed_time",
    }

    def normalize(value):
        """Mask generated identity/timing fields while comparing the remaining payload."""
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key not in volatile}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    records = []
    expected = None
    monkeypatch.setattr(factory_module.ServiceFactory, "__init__", counted_init)
    monkeypatch.setattr(factory_module, "infer_service_types", counted_infer)
    pairs = int(os.environ.get("LANGFLOW_FACTORY_BENCHMARK_PAIRS", "2"))
    try:
        # First request is recorded separately; both variants then get a warm-up.
        for pair in range(-1, pairs):
            for mode in ("eager", "lazy") if pair % 2 else ("lazy", "eager"):
                monkeypatch.setattr(deps, "get_service", eager if mode == "eager" else resolve)
                counts.update(constructors=0, inference=0)
                started = perf_counter()
                response = await client.post(
                    f"api/v1/run/{flow_id}",
                    json={
                        "input_value": "hello",
                        "input_type": "chat",
                        "output_type": "chat",
                        "session_id": str(uuid4()),
                    },
                    headers={"x-api-key": created_api_key.api_key},
                )
                milliseconds = (perf_counter() - started) * 1000
                assert response.status_code == 200, response.text
                payload = normalize(response.json())
                if expected is None:
                    expected = payload
                assert payload == expected
                records.append({"pair": pair, "mode": mode, "ms": milliseconds, **counts})
        warm = [record for record in records if record["pair"] >= 0]
        assert sum(r["constructors"] for r in warm if r["mode"] == "lazy") < sum(
            r["constructors"] for r in warm if r["mode"] == "eager"
        )
        print(json.dumps({"factory_run_samples": records}))  # noqa: T201
    finally:
        monkeypatch.setattr(deps, "get_service", resolve)
        async with deps.session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if flow:
                await session.delete(flow)


@pytest.mark.usefixtures("manager")
def test_lfx_dependency_wrapper_forwards_lazy_provider():
    """Standalone dependency resolution uses the same manager-owned lazy fallback."""
    from lfx.services.deps import get_service

    first = get_service(ServiceType.SESSION_SERVICE, default_factory=CountingFactory)
    assert first.ready
    assert get_service(ServiceType.SESSION_SERVICE, default_factory=unused_factory) is first
    assert CountingFactory.constructions == CountingFactory.creations == 1
