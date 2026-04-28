"""Unit tests for langflow.preload module.

These tests verify the failure-fallback contract and state management
of the Gunicorn master preload functionality.
"""

import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.preload import (
    _STATE,
    PreloadStep,
    _run_master_preload,
    get_owned_temp_dirs,
    is_master,
    is_preloaded,
    mark_step_complete,
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
        "bundles_loaded": _STATE.bundles_loaded,
        "types_cached": _STATE.types_cached,
        "starter_projects_created": _STATE.starter_projects_created,
        "agentic_globals_initialized": _STATE.agentic_globals_initialized,
        "agentic_mcp_configured": _STATE.agentic_mcp_configured,
        "flows_loaded": _STATE.flows_loaded,
    }

    _STATE.reset()

    yield

    for key, value in original_state.items():
        setattr(_STATE, key, value)


# ---------------------------------------------------------------------------
# Helpers for _run_master_preload() tests
# ---------------------------------------------------------------------------


@dataclass
class _PreloadFixture:
    """Bundle of mocks exposed to ``_run_master_preload()`` tests.

    Every field is a mock that stands in for a real symbol inside
    ``_run_master_preload``. Tests assert on these to verify behavior.
    """

    db_engine: AsyncMock
    db_service: MagicMock
    settings_service: MagicMock
    cache_service: MagicMock
    copy_profile_pictures: AsyncMock
    load_bundles: AsyncMock
    get_and_cache_all_types_dict: AsyncMock
    create_or_update_starter_projects: AsyncMock
    load_flows_from_directory: AsyncMock
    initialize_agentic_global_variables: AsyncMock
    auto_configure_agentic_mcp_server: AsyncMock
    logger: AsyncMock


def _async_cm(inner):
    """Build an object usable with ``async with`` that yields *inner*."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _build_db_service(dispose_side_effect=None):
    engine = AsyncMock()
    engine.dispose = AsyncMock(side_effect=dispose_side_effect)
    db_service = MagicMock()
    db_service.engine = engine
    return db_service, engine


def _build_settings_service(*, agentic_experience=False):
    settings_service = MagicMock()
    settings_service.settings.agentic_experience = agentic_experience
    settings_service.settings.components_path = []
    return settings_service


@contextmanager
def _preload_env(
    *,
    agentic_experience=False,
    dispose_side_effect=None,
    copy_profile_pictures=None,
    initialize_agentic_global_variables=None,
    auto_configure_agentic_mcp_server=None,
    cache_service=None,
    all_types_dict=None,
):
    """Context manager that patches every external dependency of ``_run_master_preload``.

    Each patch targets the *source module* that the ``from X import Y``
    statements inside ``_run_master_preload`` resolve against at call time.
    Yields a ``_PreloadFixture`` exposing the configured mocks.
    """
    db_service, engine = _build_db_service(dispose_side_effect=dispose_side_effect)
    settings_service = _build_settings_service(agentic_experience=agentic_experience)
    cache_service = cache_service if cache_service is not None else MagicMock()

    copy_pics = copy_profile_pictures or AsyncMock()
    load_bundles = AsyncMock(return_value=([], []))
    get_and_cache = AsyncMock()
    create_starter = AsyncMock()
    load_flows = AsyncMock()
    init_agentic = initialize_agentic_global_variables or AsyncMock()
    auto_config = auto_configure_agentic_mcp_server or AsyncMock()
    logger_mock = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("langflow.preload.logger", logger_mock))
        stack.enter_context(
            patch("langflow.services.utils.initialize_services", new_callable=AsyncMock),
        )
        stack.enter_context(
            patch("langflow.services.deps.get_settings_service", return_value=settings_service),
        )
        stack.enter_context(
            patch("langflow.services.deps.get_telemetry_service", return_value=MagicMock()),
        )
        stack.enter_context(patch("langflow.services.deps.get_db_service", return_value=db_service))
        stack.enter_context(patch("langflow.services.deps.get_service", return_value=cache_service))
        stack.enter_context(
            patch("langflow.services.deps.session_scope", return_value=_async_cm(AsyncMock())),
        )
        stack.enter_context(patch("langflow.initial_setup.setup.copy_profile_pictures", copy_pics))
        stack.enter_context(
            patch("langflow.initial_setup.setup.create_or_update_starter_projects", create_starter),
        )
        stack.enter_context(
            patch("langflow.initial_setup.setup.load_flows_from_directory", load_flows),
        )
        stack.enter_context(patch("langflow.main.load_bundles_with_error_handling", load_bundles))
        stack.enter_context(
            patch("lfx.interface.components.get_and_cache_all_types_dict", get_and_cache),
        )
        stack.enter_context(
            patch(
                "langflow.api.utils.mcp.agentic_mcp.initialize_agentic_global_variables",
                init_agentic,
            ),
        )
        stack.enter_context(
            patch(
                "langflow.api.utils.mcp.agentic_mcp.auto_configure_agentic_mcp_server",
                auto_config,
            ),
        )
        # Default ``component_cache.all_types_dict`` is None (skips starter-project branch).
        # Tests that exercise that branch must pass a truthy ``all_types_dict``.
        types_mock = MagicMock()
        types_mock.all_types_dict = all_types_dict
        stack.enter_context(patch("lfx.interface.components.component_cache", types_mock))

        yield _PreloadFixture(
            db_engine=engine,
            db_service=db_service,
            settings_service=settings_service,
            cache_service=cache_service,
            copy_profile_pictures=copy_pics,
            load_bundles=load_bundles,
            get_and_cache_all_types_dict=get_and_cache,
            create_or_update_starter_projects=create_starter,
            load_flows_from_directory=load_flows,
            initialize_agentic_global_variables=init_agentic,
            auto_configure_agentic_mcp_server=auto_config,
            logger=logger_mock,
        )


def _fail_and_close(exc):
    """Side-effect factory that closes the coroutine passed to ``asyncio.run`` then raises.

    Prevents spurious ``coroutine was never awaited`` warnings when the
    mock replaces ``asyncio.run`` and therefore never actually runs the
    underlying coroutine.
    """

    def _inner(coro, *_args, **_kwargs):
        if hasattr(coro, "close"):
            coro.close()
        raise exc

    return _inner


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_mark_step_complete_enforces_prerequisite_order():
    """Steps that declare prerequisites cannot complete while prerequisites are incomplete."""
    _STATE.reset()
    with pytest.raises(RuntimeError, match="incomplete prerequisites"):
        mark_step_complete(PreloadStep.TYPES_CACHED)


def test_mark_step_complete_succeeds_when_prerequisites_met():
    _STATE.reset()
    mark_step_complete(PreloadStep.BUNDLES)
    mark_step_complete(PreloadStep.TYPES_CACHED)
    assert _STATE.types_cached is True


def test_is_preloaded_false_by_default():
    assert is_preloaded() is False


def test_is_preloaded_true_after_preload():
    _STATE.preloaded = True
    assert is_preloaded() is True


def test_is_master_false_by_default():
    assert is_master() is False


def test_is_master_true_in_master_process():
    _STATE.master_pid = os.getpid()
    assert is_master() is True


def test_is_master_false_in_worker_process():
    _STATE.master_pid = os.getpid() + 1
    assert is_master() is False


def test_get_owned_temp_dirs_master_owns_dirs():
    fake_temp_dir = MagicMock()
    _STATE.preloaded = True
    _STATE.master_pid = os.getpid()
    _STATE.temp_dirs = [fake_temp_dir]

    assert get_owned_temp_dirs() == [fake_temp_dir]


def test_get_owned_temp_dirs_worker_owns_nothing():
    fake_temp_dir = MagicMock()
    _STATE.preloaded = True
    _STATE.master_pid = os.getpid() + 1
    _STATE.temp_dirs = [fake_temp_dir]

    assert get_owned_temp_dirs() == []


def test_get_owned_temp_dirs_not_preloaded():
    fake_temp_dir = MagicMock()
    _STATE.preloaded = False
    _STATE.temp_dirs = [fake_temp_dir]

    assert get_owned_temp_dirs() == []


# ---------------------------------------------------------------------------
# _PreloadState.reset() tests
# ---------------------------------------------------------------------------


def test_reset_clears_all_fields():
    """reset() must clear every field, not just preloaded/master_pid."""
    _STATE.preloaded = True
    _STATE.master_pid = 12345
    _STATE.temp_dirs = [MagicMock()]
    _STATE.bundles_components_paths = ["/a"]
    _STATE.profile_pictures_copied = True
    _STATE.bundles_loaded = True
    _STATE.types_cached = True
    _STATE.starter_projects_created = True
    _STATE.agentic_globals_initialized = True
    _STATE.agentic_mcp_configured = True
    _STATE.flows_loaded = True

    _STATE.reset()

    assert _STATE.preloaded is False
    assert _STATE.master_pid is None
    assert _STATE.temp_dirs == []
    assert _STATE.bundles_components_paths == []
    assert _STATE.profile_pictures_copied is False
    assert _STATE.bundles_loaded is False
    assert _STATE.types_cached is False
    assert _STATE.starter_projects_created is False
    assert _STATE.agentic_globals_initialized is False
    assert _STATE.agentic_mcp_configured is False
    assert _STATE.flows_loaded is False


def test_reset_cleanup_calls_temp_directories():
    """reset() must call cleanup() on each TemporaryDirectory before dropping references."""
    tmp_a = MagicMock()
    tmp_b = MagicMock()
    _STATE.temp_dirs = [tmp_a, tmp_b]

    _STATE.reset()

    tmp_a.cleanup.assert_called_once_with()
    tmp_b.cleanup.assert_called_once_with()
    assert _STATE.temp_dirs == []


# ---------------------------------------------------------------------------
# preload_master() function tests
# ---------------------------------------------------------------------------


@patch("langflow.preload.asyncio.run")
def test_preload_master_idempotent(mock_asyncio_run):
    """preload_master() should be a no-op when already preloaded."""
    _STATE.preloaded = True

    preload_master()

    mock_asyncio_run.assert_not_called()


@patch("langflow.preload.asyncio.run")
def test_preload_master_sets_state_on_success(mock_asyncio_run):
    mock_asyncio_run.return_value = None

    preload_master()

    assert _STATE.preloaded is True
    assert _STATE.master_pid == os.getpid()
    mock_asyncio_run.assert_called_once()


@patch("langflow.preload.logger")
@patch("langflow.preload.asyncio.run")
def test_preload_master_no_flag_on_failure(mock_asyncio_run, mock_logger):
    """preload_master() must NOT set preloaded flag when preload fails."""
    mock_asyncio_run.side_effect = _fail_and_close(RuntimeError("Preload failed"))

    preload_master()

    assert _STATE.preloaded is False
    mock_logger.exception.assert_called_once()


@patch("langflow.preload.logger")
@patch("langflow.preload.asyncio.run")
@pytest.mark.usefixtures("reset_preload_state")
def test_preload_master_resets_state_on_failure(mock_asyncio_run, _mock_logger):  # noqa: PT019
    """preload_master() resets _STATE on failure to keep is_master() and is_preloaded() consistent.

    Without reset(), master_pid stays set (truthy is_master()) while
    preloaded stays False, and best-effort completion flags set before the
    failure point remain True — causing workers to silently skip re-running
    those steps.
    """
    _STATE.profile_pictures_copied = True
    _STATE.bundles_loaded = True
    mock_asyncio_run.side_effect = _fail_and_close(RuntimeError("boom"))

    preload_master()

    assert _STATE.preloaded is False
    assert _STATE.master_pid is None
    assert _STATE.profile_pictures_copied is False
    assert _STATE.bundles_loaded is False
    assert is_master() is False
    assert is_preloaded() is False


@patch("langflow.preload.gc")
@patch("langflow.preload.asyncio.run")
def test_preload_master_calls_gc_freeze(mock_asyncio_run, mock_gc):
    mock_asyncio_run.return_value = None

    preload_master()

    mock_gc.collect.assert_called_once()
    mock_gc.freeze.assert_called_once()


@patch("langflow.preload.gc")
@patch("langflow.preload.logger")
@patch("langflow.preload.asyncio.run")
def test_preload_master_resets_state_when_gc_freeze_fails(mock_asyncio_run, mock_logger, mock_gc):
    """If gc.freeze() fails after async preload, state is reset and the exception propagates."""
    mock_asyncio_run.return_value = None
    mock_gc.freeze.side_effect = RuntimeError("gc.freeze() failed")

    with pytest.raises(RuntimeError, match=r"gc\.freeze\(\) failed"):
        preload_master()

    assert _STATE.preloaded is False
    assert _STATE.master_pid is None
    mock_logger.exception.assert_called()


# ---------------------------------------------------------------------------
# _run_master_preload() — Failure-Fallback Contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_master_preload_disposes_db_engine():
    """DB engine must be disposed before the master returns."""
    with _preload_env() as fx:
        await _run_master_preload()

    fx.db_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_master_preload_critical_step_failure_propagates():
    """A failure in a critical fork-safety step (DB dispose) must propagate."""
    with (
        _preload_env(dispose_side_effect=RuntimeError("Failed to dispose DB engine")),
        pytest.raises(RuntimeError, match="Failed to dispose DB engine"),
    ):
        await _run_master_preload()


@pytest.mark.asyncio
async def test_run_master_preload_best_effort_step_failure_continues():
    """A best-effort step failure logs an exception with traceback and lets preload continue.

    The completion flag for the failed step must remain False so workers
    re-run it during their lifespan. Critical steps (DB dispose) must
    still run afterwards.
    """
    failing_copy = AsyncMock(side_effect=RuntimeError("Failed to copy profile pictures"))

    with _preload_env(copy_profile_pictures=failing_copy) as fx:
        await _run_master_preload()

    assert any("copy_profile_pictures failed" in str(call) for call in fx.logger.aexception.call_args_list)
    assert _STATE.profile_pictures_copied is False
    fx.db_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_master_preload_sets_completion_flags_on_success():
    """Every successful step must set its matching completion flag."""
    with _preload_env(all_types_dict={"fake": "types_dict"}):
        await _run_master_preload()

    assert _STATE.profile_pictures_copied is True
    assert _STATE.bundles_loaded is True
    assert _STATE.types_cached is True
    assert _STATE.starter_projects_created is True
    assert _STATE.flows_loaded is True


@pytest.mark.asyncio
async def test_run_master_preload_closes_external_cache_service():
    """An ExternalAsyncBaseCacheService must have teardown() awaited before fork."""
    from langflow.services.cache.base import ExternalAsyncBaseCacheService

    class _FakeCache(ExternalAsyncBaseCacheService):
        """Minimal concrete subclass so isinstance() succeeds without mocking.

        The method arguments mirror the abstract base signatures; ruff's
        ARG002 is silenced because these are deliberately inert stubs.
        """

        teardown = AsyncMock()

        async def is_connected(self):
            return True

        async def get(self, key, lock=None):  # noqa: ARG002
            return None

        async def set(self, key, value, lock=None):  # noqa: ARG002
            return None

        async def upsert(self, key, value, lock=None):  # noqa: ARG002
            return None

        async def delete(self, key, lock=None):  # noqa: ARG002
            return None

        async def clear(self, lock=None):  # noqa: ARG002
            return None

        async def contains(self, key):  # noqa: ARG002
            return False

    fake_cache = _FakeCache()

    with _preload_env(cache_service=fake_cache):
        await _run_master_preload()

    fake_cache.teardown.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_master_preload_agentic_experience_enabled():
    """Both agentic steps run and set their flags when ``agentic_experience`` is True."""
    init_agentic = AsyncMock()
    auto_config = AsyncMock()

    with _preload_env(
        agentic_experience=True,
        all_types_dict={"fake": "types_dict"},
        initialize_agentic_global_variables=init_agentic,
        auto_configure_agentic_mcp_server=auto_config,
    ):
        await _run_master_preload()

    init_agentic.assert_awaited_once()
    auto_config.assert_awaited_once()
    assert _STATE.agentic_globals_initialized is True
    assert _STATE.agentic_mcp_configured is True


@pytest.mark.asyncio
async def test_run_master_preload_agentic_partial_failure_tracked_separately():
    """Independent try/except per agentic step: one failing must not block the other.

    Guards the "split the one-try-wraps-two-ops block into two tries" claim.
    """
    init_agentic = AsyncMock(side_effect=RuntimeError("agentic globals broke"))
    auto_config = AsyncMock()

    with _preload_env(
        agentic_experience=True,
        all_types_dict={"fake": "types_dict"},
        initialize_agentic_global_variables=init_agentic,
        auto_configure_agentic_mcp_server=auto_config,
    ):
        await _run_master_preload()

    init_agentic.assert_awaited_once()
    auto_config.assert_awaited_once()
    assert _STATE.agentic_globals_initialized is False
    assert _STATE.agentic_mcp_configured is True
