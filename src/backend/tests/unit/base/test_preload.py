"""Unit tests for langflow.preload module.

These tests verify the failure-fallback contract and state management
of the Gunicorn master preload functionality.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.preload import (
    _STATE,
    _run_master_preload,
    get_owned_temp_dirs,
    get_preloaded_temp_dirs,
    is_master,
    is_preloaded,
    preload_master,
)


@pytest.fixture(autouse=True)
def reset_preload_state():
    """Reset the preload state before and after each test."""
    original_state = {
        "preloaded": _STATE.preloaded,
        "master_pid": _STATE.master_pid,
        "temp_dirs": _STATE.temp_dirs.copy(),
        "bundles_components_paths": _STATE.bundles_components_paths.copy(),
        "profile_pictures_copied": _STATE.profile_pictures_copied,
        "starter_projects_created": _STATE.starter_projects_created,
        "agentic_globals_initialized": _STATE.agentic_globals_initialized,
        "agentic_mcp_configured": _STATE.agentic_mcp_configured,
        "flows_loaded": _STATE.flows_loaded,
    }

    # Reset to defaults
    _STATE.preloaded = False
    _STATE.master_pid = None
    _STATE.temp_dirs = []
    _STATE.bundles_components_paths = []
    _STATE.profile_pictures_copied = False
    _STATE.starter_projects_created = False
    _STATE.agentic_globals_initialized = False
    _STATE.agentic_mcp_configured = False
    _STATE.flows_loaded = False

    yield

    # Restore original state
    _STATE.preloaded = original_state["preloaded"]
    _STATE.master_pid = original_state["master_pid"]
    _STATE.temp_dirs = original_state["temp_dirs"]
    _STATE.bundles_components_paths = original_state["bundles_components_paths"]
    _STATE.profile_pictures_copied = original_state["profile_pictures_copied"]
    _STATE.starter_projects_created = original_state["starter_projects_created"]
    _STATE.agentic_globals_initialized = original_state["agentic_globals_initialized"]
    _STATE.agentic_mcp_configured = original_state["agentic_mcp_configured"]
    _STATE.flows_loaded = original_state["flows_loaded"]


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_is_preloaded_false_by_default():
    """is_preloaded() should return False when preload hasn't run."""
    assert is_preloaded() is False


def test_is_preloaded_true_after_preload():
    """is_preloaded() should return True after successful preload."""
    _STATE.preloaded = True
    assert is_preloaded() is True


def test_is_master_false_by_default():
    """is_master() should return False when master_pid is not set."""
    assert is_master() is False


def test_is_master_true_in_master_process():
    """is_master() should return True when called in the master process."""
    _STATE.master_pid = os.getpid()
    assert is_master() is True


def test_is_master_false_in_worker_process():
    """is_master() should return False when called in a forked worker."""
    _STATE.master_pid = os.getpid() + 1  # Simulate different PID
    assert is_master() is False


def test_get_preloaded_temp_dirs_empty_by_default():
    """get_preloaded_temp_dirs() should return empty list before preload."""
    assert get_preloaded_temp_dirs() == []


def test_get_preloaded_temp_dirs_returns_list():
    """get_preloaded_temp_dirs() should return the temp_dirs list."""
    fake_temp_dir = MagicMock()
    _STATE.temp_dirs = [fake_temp_dir]
    result = get_preloaded_temp_dirs()
    assert result == [fake_temp_dir]


def test_get_owned_temp_dirs_master_owns_dirs():
    """get_owned_temp_dirs() should return temp_dirs when called in master."""
    fake_temp_dir = MagicMock()
    _STATE.preloaded = True
    _STATE.master_pid = os.getpid()
    _STATE.temp_dirs = [fake_temp_dir]

    result = get_owned_temp_dirs()
    assert result == [fake_temp_dir]


def test_get_owned_temp_dirs_worker_owns_nothing():
    """get_owned_temp_dirs() should return empty list when called in worker."""
    fake_temp_dir = MagicMock()
    _STATE.preloaded = True
    _STATE.master_pid = os.getpid() + 1  # Simulate worker
    _STATE.temp_dirs = [fake_temp_dir]

    result = get_owned_temp_dirs()
    assert result == []


def test_get_owned_temp_dirs_not_preloaded():
    """get_owned_temp_dirs() should return empty list when not preloaded."""
    fake_temp_dir = MagicMock()
    _STATE.preloaded = False
    _STATE.temp_dirs = [fake_temp_dir]

    result = get_owned_temp_dirs()
    assert result == []


# ---------------------------------------------------------------------------
# preload_master() function tests
# ---------------------------------------------------------------------------


@patch("langflow.preload.asyncio.run")
def test_preload_master_idempotent(mock_asyncio_run):
    """preload_master() should be idempotent (no-op on subsequent calls)."""
    _STATE.preloaded = True

    preload_master()

    # Should not call asyncio.run if already preloaded
    mock_asyncio_run.assert_not_called()


@patch("langflow.preload.asyncio.run")
def test_preload_master_sets_state_on_success(mock_asyncio_run):
    """preload_master() should set preloaded flag on success."""
    mock_asyncio_run.return_value = None  # Simulate successful completion

    preload_master()

    assert _STATE.preloaded is True
    assert _STATE.master_pid == os.getpid()
    mock_asyncio_run.assert_called_once()


@patch("langflow.preload.logger")
@patch("langflow.preload.asyncio.run")
def test_preload_master_no_flag_on_failure(mock_asyncio_run, mock_logger):
    """preload_master() should NOT set preloaded flag if preload fails.

    This verifies the failure-fallback contract: if preload fails,
    workers will fall back to running full lifespan initialization.
    """
    mock_asyncio_run.side_effect = RuntimeError("Preload failed")

    preload_master()

    assert _STATE.preloaded is False
    mock_logger.exception.assert_called_once()


@patch("langflow.preload.gc")
@patch("langflow.preload.asyncio.run")
def test_preload_master_calls_gc_freeze(mock_asyncio_run, mock_gc):
    """preload_master() should call gc.freeze() after successful preload."""
    mock_asyncio_run.return_value = None

    preload_master()

    mock_gc.collect.assert_called_once()
    mock_gc.freeze.assert_called_once()


@patch("langflow.preload.gc")
@patch("langflow.preload.logger")
@patch("langflow.preload.asyncio.run")
def test_preload_master_continues_if_gc_freeze_fails(mock_asyncio_run, mock_logger, mock_gc):
    """preload_master() should continue (not abort) if gc.freeze() fails.

    gc.freeze() failure is not critical, so preload should still succeed.
    """
    mock_asyncio_run.return_value = None
    mock_gc.freeze.side_effect = RuntimeError("gc.freeze() failed")

    preload_master()

    assert _STATE.preloaded is True  # Should still succeed
    mock_logger.exception.assert_called()


# ---------------------------------------------------------------------------
# _run_master_preload() function tests - Failure-Fallback Contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
async def test_run_master_preload_disposes_db_engine(
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() must dispose DB engine before returning.

    This is CRITICAL for fork-safety. Failure to dispose the engine
    should propagate and abort preload.
    """
    mock_engine = AsyncMock()
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = False
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None

    # Mock all the setup functions to avoid actual operations
    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock),
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.get_service"),
    ):
        mock_load_bundles.return_value = ([], [])
        await _run_master_preload()

    # Verify DB engine was disposed
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
async def test_run_master_preload_critical_step_failure_propagates(
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() should propagate exceptions from critical steps.

    If DB engine disposal fails, the exception should propagate and
    abort preload, forcing workers to fall back to full initialization.
    """
    mock_engine = AsyncMock()
    mock_engine.dispose.side_effect = RuntimeError("Failed to dispose DB engine")
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = False
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None

    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock),
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.get_service"),
    ):
        mock_load_bundles.return_value = ([], [])
        with pytest.raises(RuntimeError, match="Failed to dispose DB engine"):
            await _run_master_preload()


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
@patch("langflow.preload.logger")
async def test_run_master_preload_best_effort_step_failure_continues(
    mock_logger,
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() should continue if best-effort steps fail.

    Best-effort steps (profile pictures, starter projects, etc.) should
    log a warning and clear their completion flag, but not abort preload.
    Workers will re-run incomplete steps during their lifespan.
    """
    mock_engine = AsyncMock()
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = False
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None

    # Mock copy_profile_pictures to fail
    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock) as mock_copy_pics,
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.get_service"),
    ):
        mock_copy_pics.side_effect = RuntimeError("Failed to copy profile pictures")
        mock_load_bundles.return_value = ([], [])
        # Should NOT raise exception
        await _run_master_preload()

    # Verify warning was logged
    assert any("copy_profile_pictures failed" in str(call) for call in mock_logger.awarning.call_args_list)

    # Verify completion flag was NOT set (workers will re-run this step)
    assert _STATE.profile_pictures_copied is False

    # Verify DB engine was still disposed (critical step)
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
@patch("langflow.preload.component_cache")
async def test_run_master_preload_sets_completion_flags_on_success(
    mock_component_cache,
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() should set completion flags for successful steps.

    This verifies that workers inherit the completion state and can
    skip redundant initialization for steps that completed during preload.
    """
    mock_engine = AsyncMock()
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = False
    mock_settings_service.settings.components_path = []
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None

    # Mock component_cache.all_types_dict
    mock_component_cache.all_types_dict = {"fake": "types_dict"}

    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock),
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.create_or_update_starter_projects", new_callable=AsyncMock),
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.get_service"),
    ):
        mock_load_bundles.return_value = ([], [])
        await _run_master_preload()

    # Verify completion flags were set
    assert _STATE.profile_pictures_copied is True
    assert _STATE.starter_projects_created is True
    assert _STATE.flows_loaded is True


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
async def test_run_master_preload_closes_cache_service_socket(
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() should teardown external cache service before fork.

    This is CRITICAL for fork-safety with Redis or other external cache services.
    """
    mock_engine = AsyncMock()
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = False
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None

    # Mock cache service with teardown method
    mock_cache_service = MagicMock()
    mock_teardown = AsyncMock()
    mock_cache_service.teardown = mock_teardown

    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock),
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.get_service") as mock_get_service,
        patch("langflow.preload.ExternalAsyncBaseCacheService") as mock_base_class,
    ):
        mock_load_bundles.return_value = ([], [])
        mock_get_service.return_value = mock_cache_service
        # Make isinstance check pass
        mock_base_class.__instancecheck__ = lambda *_args: True

        await _run_master_preload()

    # Verify teardown was called
    mock_teardown.assert_called_once()


@pytest.mark.asyncio
@patch("langflow.preload.get_db_service")
@patch("langflow.preload.get_settings_service")
@patch("langflow.preload.initialize_services")
@patch("langflow.preload.component_cache")
async def test_run_master_preload_agentic_experience_enabled(
    mock_component_cache,
    mock_initialize_services,
    mock_get_settings_service,
    mock_get_db_service,
):
    """_run_master_preload() should initialize agentic features when enabled."""
    mock_engine = AsyncMock()
    mock_db_service = MagicMock()
    mock_db_service.engine = mock_engine
    mock_get_db_service.return_value = mock_db_service

    mock_settings_service = MagicMock()
    mock_settings_service.settings.agentic_experience = True  # Enable agentic
    mock_settings_service.settings.components_path = []
    mock_get_settings_service.return_value = mock_settings_service

    mock_initialize_services.return_value = None
    mock_component_cache.all_types_dict = {"fake": "types_dict"}

    with (
        patch("langflow.preload.copy_profile_pictures", new_callable=AsyncMock),
        patch("langflow.preload.load_bundles_with_error_handling", new_callable=AsyncMock) as mock_load_bundles,
        patch("langflow.preload.get_and_cache_all_types_dict", new_callable=AsyncMock),
        patch("langflow.preload.create_or_update_starter_projects", new_callable=AsyncMock),
        patch("langflow.preload.initialize_agentic_global_variables", new_callable=AsyncMock) as mock_init_agentic,
        patch("langflow.preload.auto_configure_agentic_mcp_server", new_callable=AsyncMock) as mock_auto_config,
        patch("langflow.preload.load_flows_from_directory", new_callable=AsyncMock),
        patch("langflow.preload.session_scope") as mock_session_scope,
        patch("langflow.preload.get_service"),
    ):
        mock_load_bundles.return_value = ([], [])
        mock_session = AsyncMock()
        mock_session_scope.return_value.__aenter__.return_value = mock_session

        await _run_master_preload()

    # Verify agentic functions were called
    mock_init_agentic.assert_called_once()
    mock_auto_config.assert_called_once()

    # Verify completion flags
    assert _STATE.agentic_globals_initialized is True
    assert _STATE.agentic_mcp_configured is True
