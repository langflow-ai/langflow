"""Regression test for issue #13634 (Bug 2): the masking ``UnboundLocalError``.

When startup fails before bundle loading assigns ``temp_dirs``, the shutdown
``finally`` block in ``lifespan`` iterates ``temp_dirs`` during temp-file cleanup.
Previously ``temp_dirs`` was only bound inside the ``try``, so an early failure
(such as an unresolvable ``LANGFLOW_DATABASE_URL``) caused the cleanup to raise
``UnboundLocalError: cannot access local variable 'temp_dirs'`` -- a second,
confusing error logged on top of the real one.

Binding ``temp_dirs = []`` before the ``try`` fixes this. This test drives the
real ``lifespan`` context manager with a failing ``initialize_services`` and
asserts the cleanup path no longer raises.

Issue: https://github.com/langflow-ai/langflow/issues/13634
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import langflow.main as main_module
import pytest
import structlog


async def test_startup_failure_does_not_mask_error_with_unbound_temp_dirs(monkeypatch):
    lifespan = main_module.get_lifespan()

    sentinel = RuntimeError("Error creating DB and tables")
    cleanup_logger = AsyncMock()
    monkeypatch.setattr(main_module.logger, "aexception", cleanup_logger)

    async def _failing_initialize_services(*_args, **_kwargs):
        raise sentinel

    # Force an early startup failure (before bundle loading binds temp_dirs).
    monkeypatch.setattr(main_module, "initialize_services", _failing_initialize_services)
    # Replace destructive/heavy shutdown calls so the finally block runs in
    # isolation without tearing down services shared by the wider test session.
    monkeypatch.setattr(main_module, "teardown_services", AsyncMock())
    monkeypatch.setattr(main_module, "cleanup_mcp_sessions", AsyncMock())

    with pytest.raises(RuntimeError, match="Error creating DB and tables") as exc_info:
        async with lifespan(object()):
            pass

    # The real startup error propagates unchanged...
    assert exc_info.value is sentinel

    # ...and cleanup did not raise a secondary exception that the outer cleanup
    # handler would report as an unhandled lifespan cleanup error.
    assert not any(
        call.args and "Unhandled error during cleanup" in str(call.args[0]) for call in cleanup_logger.await_args_list
    )


async def test_environment_import_failure_does_not_abort_worker_startup(monkeypatch):
    """The real worker lifespan continues past a failed environment sweep."""
    from langflow.preload import _STATE

    monkeypatch.setattr(_STATE, "environment_variables_initialized", False)
    sweep = AsyncMock(side_effect=RuntimeError("environment import failed"))
    variable_service = AsyncMock(initialize_all_user_variables=sweep)
    monkeypatch.setattr("langflow.services.deps.get_variable_service", lambda: variable_service)
    monkeypatch.setattr(main_module, "initialize_services", AsyncMock())
    reached_next_step = RuntimeError("reached next startup step")

    async def stop_after_services(message, *_args, **_kwargs):
        if message.startswith("Services initialized in"):
            raise reached_next_step

    logger = AsyncMock()
    logger.exception = MagicMock()
    logger.adebug.side_effect = stop_after_services
    monkeypatch.setattr(main_module, "logger", logger)
    monkeypatch.setattr(main_module, "teardown_services", AsyncMock())
    monkeypatch.setattr(main_module, "cleanup_mcp_sessions", AsyncMock())
    with pytest.raises(RuntimeError, match="reached next startup step") as exc:
        async with main_module.get_lifespan()(object()):
            pass
    assert exc.value is reached_next_step
    sweep.assert_awaited_once()
    assert _STATE.environment_variables_initialized is False


@pytest.mark.parametrize("failure", ["migration", "pools"])
async def test_storage_shutdown_failure_does_not_skip_later_cleanup(monkeypatch, failure):
    """Drive the real lifespan's finally block with a failing storage shutdown step."""
    from langflow.services.knowledge_base_storage import coordinator, runtime

    warning_logger = structlog.make_filtering_bound_logger(logging.WARNING)(structlog.ReturnLogger(), [], {})
    monkeypatch.setattr(main_module, "logger", warning_logger)
    sentinel = RuntimeError("startup failed before bundle loading")
    monkeypatch.setattr(main_module, "initialize_services", AsyncMock(side_effect=sentinel))
    monkeypatch.setattr(main_module, "cleanup_mcp_sessions", AsyncMock())
    teardown = AsyncMock()
    lag_monitor = AsyncMock()
    sandbox = MagicMock()
    progress = MagicMock()
    monkeypatch.setattr(main_module, "teardown_services", teardown)
    monkeypatch.setattr(main_module, "stop_event_loop_lag_monitor", lag_monitor)
    monkeypatch.setattr("lfx.utils.sandbox.shutdown_sandbox", sandbox)
    monkeypatch.setattr("langflow.cli.progress.create_langflow_shutdown_progress", lambda **_kwargs: progress)
    stop_upgrade = AsyncMock(side_effect=RuntimeError("stop failed") if failure == "migration" else None)
    close_pools = AsyncMock(side_effect=RuntimeError("dispose failed") if failure == "pools" else None)
    monkeypatch.setattr(coordinator, "stop_upgrade", stop_upgrade)
    monkeypatch.setattr(runtime, "close_coordination_pools", close_pools)

    with pytest.raises(RuntimeError) as exc:
        async with main_module.get_lifespan()(object()):
            pass
    assert exc.value is sentinel
    stop_upgrade.assert_awaited_once()
    close_pools.assert_awaited_once()
    lag_monitor.assert_awaited_once()
    teardown.assert_awaited_once()
    sandbox.assert_called_once()
    assert [call.args[0] for call in progress.step.call_args_list] == list(range(5))
