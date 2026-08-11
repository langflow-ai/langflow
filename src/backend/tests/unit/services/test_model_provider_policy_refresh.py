from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from langflow.services.task import model_provider_policy_refresh as refresh_module
from lfx.services.model_provider_policy import (
    BaseModelProviderPolicyService,
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicyService,
)
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot


class _DatabaseOwnedPluginPolicyService(BaseModelProviderPolicyService):
    def __init__(self, policy_bundle_service: PolicyBundleService) -> None:
        super().__init__()
        self.policy_bundle_service = policy_bundle_service
        self.set_ready()

    def get_allowed_provider_ids(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> frozenset[str]:
        _ = context, purpose
        if not self.policy_bundle_service.source_available:
            return frozenset()
        ceiling = self.policy_bundle_service.snapshot.approved_provider_ids
        return candidate_provider_ids if not ceiling else candidate_provider_ids & ceiling


class _ExternalBuiltinPolicyService(ModelProviderPolicyService):
    def __init__(self) -> None:
        super().__init__()
        self.set_approved_provider_ids({"openai"}, version=2)

    @property
    def external_approved_provider_ids(self) -> frozenset[str]:
        return frozenset({"openai"})


async def test_refresh_failure_preserves_unrestricted_policy_availability(monkeypatch):
    service = ModelProviderPolicyService()
    error_message = "policy store unavailable"

    @asynccontextmanager
    async def failing_session_scope():
        raise ConnectionError(error_message)
        yield

    monkeypatch.setattr(refresh_module, "session_scope", failing_session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is False
    assert service.policy_source_available is True


async def test_missing_policy_singleton_denies_an_unrestricted_service(monkeypatch):
    service = ModelProviderPolicyService()
    error_message = "model-provider policy singleton is missing"

    @asynccontextmanager
    async def failing_session_scope():
        raise refresh_module.ModelProviderPolicyNotInitializedError(error_message)
        yield

    monkeypatch.setattr(refresh_module, "session_scope", failing_session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert service.policy_source_available is False


async def test_refresh_apply_failure_denies_a_restrictive_policy(monkeypatch):
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"}, version=3)

    @asynccontextmanager
    async def session_scope():
        yield object()

    monkeypatch.setattr(refresh_module, "session_scope", session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(
        refresh_module,
        "get_model_provider_policy_state",
        AsyncMock(return_value=SimpleNamespace(approved_provider_ids=frozenset({"openai"}))),
    )
    monkeypatch.setattr(
        refresh_module,
        "apply_model_provider_policy_state",
        Mock(side_effect=RuntimeError("apply failed")),
    )
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert service.policy_source_available is False


async def test_refresh_apply_failure_denies_a_newly_read_restrictive_policy(monkeypatch):
    service = ModelProviderPolicyService()

    @asynccontextmanager
    async def session_scope():
        yield object()

    state = SimpleNamespace(approved_provider_ids=frozenset({"openai"}))
    monkeypatch.setattr(refresh_module, "session_scope", session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(
        refresh_module,
        "get_model_provider_policy_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        refresh_module,
        "apply_model_provider_policy_state",
        Mock(side_effect=RuntimeError("apply failed")),
    )
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert service.approved_provider_ids == frozenset()
    assert changed is True
    assert service.policy_source_available is False


async def test_refresh_loop_survives_an_iteration_failure(monkeypatch):
    worker = refresh_module.ModelProviderPolicyRefreshWorker(interval=0.001)
    calls = 0
    error_message = "apply failed"

    async def run_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError(error_message)
        worker._stop_event.set()
        return False

    monkeypatch.setattr(worker, "_run_once", run_once)
    log_error = AsyncMock()
    monkeypatch.setattr(refresh_module.logger, "aerror", log_error)

    await asyncio.wait_for(worker._run(), timeout=1)

    assert calls == 2
    log_error.assert_awaited_once()


async def test_start_uses_configured_interval_and_stop_clears_task(monkeypatch):
    service = ModelProviderPolicyService()
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(model_provider_policy_refresh_interval_s=7.5),
    )
    worker = refresh_module.ModelProviderPolicyRefreshWorker()
    run_started = asyncio.Event()
    keep_running = asyncio.Event()

    async def run():
        run_started.set()
        await keep_running.wait()

    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module, "get_settings_service", lambda: settings_service)
    monkeypatch.setattr(worker, "_run", run)

    await worker.start()
    await run_started.wait()

    assert worker._active_interval == 7.5
    assert worker._task is not None

    await worker.stop()

    assert worker._task is None


async def test_start_refreshes_a_database_owned_provider_plugin(monkeypatch):
    service = _DatabaseOwnedPluginPolicyService(PolicyBundleService())
    worker = refresh_module.ModelProviderPolicyRefreshWorker(interval=5)
    run_started = asyncio.Event()
    keep_running = asyncio.Event()

    async def run():
        run_started.set()
        await keep_running.wait()

    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(worker, "_run", run)

    await worker.start()
    await run_started.wait()

    assert worker._task is not None

    await worker.stop()


async def test_refresh_failure_marks_a_restrictive_database_owned_plugin_unavailable(monkeypatch):
    bundle_service = PolicyBundleService()
    bundle_service.publish(
        PolicyBundleSnapshot(
            revision=3,
            initialized=True,
            source="api",
            approved_provider_ids=frozenset({"openai"}),
        )
    )
    service = _DatabaseOwnedPluginPolicyService(bundle_service)
    error_message = "policy store unavailable"

    @asynccontextmanager
    async def failing_session_scope():
        raise ConnectionError(error_message)
        yield

    invalidate = Mock(wraps=service.invalidate)
    monkeypatch.setattr(service, "invalidate", invalidate)
    monkeypatch.setattr(refresh_module, "session_scope", failing_session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module, "get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert bundle_service.source_available is False
    invalidate.assert_called_once_with()


async def test_start_skips_explicitly_external_builtin_subclass(monkeypatch):
    service = _ExternalBuiltinPolicyService()
    worker = refresh_module.ModelProviderPolicyRefreshWorker()
    debug = AsyncMock()
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(
        refresh_module,
        "get_catalog_policy_service",
        lambda: SimpleNamespace(external_policy_snapshot=object()),
    )
    monkeypatch.setattr(refresh_module.logger, "adebug", debug)

    await worker.start()

    assert worker._task is None
    debug.assert_awaited_once_with(
        "Policy-bundle refresh worker not started: provider and catalog policies are externally managed"
    )


async def test_start_refreshes_database_catalog_when_provider_policy_is_external(monkeypatch):
    service = _ExternalBuiltinPolicyService()
    worker = refresh_module.ModelProviderPolicyRefreshWorker(interval=5)
    run_started = asyncio.Event()
    keep_running = asyncio.Event()

    async def run():
        run_started.set()
        await keep_running.wait()

    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(
        refresh_module,
        "get_catalog_policy_service",
        lambda: SimpleNamespace(external_policy_snapshot=None),
    )
    monkeypatch.setattr(worker, "_run", run)

    await worker.start()
    await run_started.wait()

    assert worker._task is not None

    await worker.stop()


async def test_refresh_failure_does_not_fail_close_explicitly_external_builtin_subclass(monkeypatch):
    service = _ExternalBuiltinPolicyService()
    error_message = "policy store unavailable"

    @asynccontextmanager
    async def failing_session_scope():
        raise ConnectionError(error_message)
        yield

    fail_closed = Mock(wraps=service.fail_closed)
    monkeypatch.setattr(service, "fail_closed", fail_closed)
    monkeypatch.setattr(refresh_module, "session_scope", failing_session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module.logger, "aerror", AsyncMock())

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is False
    assert service.approved_provider_ids == frozenset({"openai"})
    fail_closed.assert_not_called()


async def test_start_replaces_a_completed_refresh_task(monkeypatch):
    service = ModelProviderPolicyService()
    worker = refresh_module.ModelProviderPolicyRefreshWorker(interval=5)
    previous = asyncio.create_task(asyncio.sleep(0))
    await previous
    worker._task = previous
    run_started = asyncio.Event()
    keep_running = asyncio.Event()

    async def run():
        run_started.set()
        await keep_running.wait()

    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(worker, "_run", run)

    await worker.start()
    await run_started.wait()

    assert worker._task is not previous
    assert worker._task is not None

    await worker.stop()


async def test_stop_clears_a_failed_task_without_reraising():
    worker = refresh_module.ModelProviderPolicyRefreshWorker(interval=5)
    error_message = "task failed"

    async def fail():
        raise RuntimeError(error_message)

    task = asyncio.create_task(fail())
    await asyncio.sleep(0)
    worker._task = task

    await worker.stop()

    assert worker._task is None
