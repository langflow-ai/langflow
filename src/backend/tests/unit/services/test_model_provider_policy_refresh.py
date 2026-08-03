from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from langflow.services.task import model_provider_policy_refresh as refresh_module
from lfx.services.model_provider_policy import ModelProviderPolicyService


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


async def test_start_skips_explicitly_external_builtin_subclass(monkeypatch):
    service = _ExternalBuiltinPolicyService()
    worker = refresh_module.ModelProviderPolicyRefreshWorker()
    debug = AsyncMock()
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(refresh_module.logger, "adebug", debug)

    await worker.start()

    assert worker._task is None
    debug.assert_awaited_once_with("Model-provider policy refresh worker not started: external policy service active")


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
