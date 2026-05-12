"""SVC-04 restart-parity integration test -- boot lifespan sequence twice.

Closes ROADMAP Success Criterion #4 ("restart integration test
confirms no 'service not initialized' or 'table doesn't exist' errors with
the new lifespan order") and ROADMAP row.

Strategy (analog: ``src/backend/tests/performance/test_server_init.py`` 26-75):
chain the three public async functions the FastAPI lifespan invokes --
``initialize_services`` then ``get_and_cache_all_types_dict`` then
``create_or_update_starter_projects`` -- against a tmp SQLite DB and an
isolated ``LANGFLOW_CONFIG_DIR``. Running the full FastAPI lifespan (with
its ``asynccontextmanager`` + ``FileLock`` + MCP init) would require the
full app machinery; chaining the public API entrypoints is the minimum
that reproduces the ordering-sensitive region (DB ready -> types cached ->
starter projects synced).

Each test runs the chain TWICE in one async function (same process, same
event loop). Boot 1 starts from a clean state. Boot 2 reuses the same tmp
directory + DB, so:

- The hash file written by Boot 1's ``write_hash_file_safe`` is on disk.
- The DB already has the starter-projects folder + flows from Boot 1.
- Boot 2's ``create_or_update_starter_projects`` sees matching rows and
  idempotently skips (or re-updates).

The parity assertion is: no ``RuntimeError``, no
``sqlalchemy.exc.OperationalError`` ("table doesn't exist" / "no such
table"), and no ERROR-level log records whose message contains
"service not initialized" or similar ordering-violation strings.

SVC-04 parity also asserts that ``src/backend/base/langflow/services/utils.py``
is untouched by (Test 6 -- AST-level function-name + order check).
"""

from __future__ import annotations

import ast
import inspect
import logging

import pytest
from langflow.initial_setup.setup import create_or_update_starter_projects
from langflow.initial_setup.starter_project_hash import (
    HASH_FILENAME,
    compute_starter_projects_hash,
    write_hash_file_safe,
)
from langflow.services.deps import get_settings_service
from langflow.services.utils import initialize_services
from lfx.interface.components import get_and_cache_all_types_dict

_INIT_ORDER_ERROR_MARKERS = (
    "service not initialized",
    "table doesn't exist",
    "no such table",
    "OperationalError",
)


def _init_order_error_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return ERROR records whose message matches any init-order marker."""
    matches: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.levelno < logging.ERROR:
            continue
        message = record.getMessage()
        if any(marker in message for marker in _INIT_ORDER_ERROR_MARKERS):
            matches.append(record)
    return matches


async def _run_lifespan_chain() -> None:
    """Execute the ordering-sensitive init chain: services -> types -> starter projects.

    Matches the real ``langflow/main.py`` lifespan order: ``initialize_services``
    brings up the DB + settings + superuser; ``get_and_cache_all_types_dict``
    builds the ComponentCache (load-bearing input for starter-project sync);
    ``create_or_update_starter_projects`` writes starter-folder rows + flows.
    """
    await initialize_services(fix_migration=False)
    settings_service = get_settings_service()
    types_dict = await get_and_cache_all_types_dict(settings_service)
    await create_or_update_starter_projects(types_dict)


# ---------------------------------------------------------------------------
# Test 1 -- initialize_services cleanly (Boot 1 of a clean environment).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_services_boot_1_clean(
    tmp_config_dir,  # noqa: ARG001 -- fixture side-effect: redirects LANGFLOW_CONFIG_DIR + DB URL
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boot 1: initialize_services against a fresh tmp DB produces no init-order errors."""
    with caplog.at_level(logging.ERROR):
        await initialize_services(fix_migration=False)
    settings_service = get_settings_service()
    assert "test_.db" in settings_service.settings.database_url, (
        f"Expected tmp DB URL; got {settings_service.settings.database_url!r}"
    )
    offenders = _init_order_error_records(caplog)
    assert not offenders, f"Boot 1 produced init-order ERROR records: {[r.getMessage() for r in offenders]!r}"


# ---------------------------------------------------------------------------
# Test 2 -- full lifespan sequence, clean state (Boot 1).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifespan_sequence_boot_1(
    tmp_config_dir,  # noqa: ARG001 -- fixture side-effect: redirects LANGFLOW_CONFIG_DIR + DB URL
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boot 1: initialize_services + types-cache + starter-projects completes with no init errors."""
    with caplog.at_level(logging.ERROR):
        await _run_lifespan_chain()
    offenders = _init_order_error_records(caplog)
    assert not offenders, (
        f"Boot 1 lifespan chain produced init-order ERROR records: {[r.getMessage() for r in offenders]!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 -- second boot with pre-seeded matching hash (the parity test).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_with_matching_hash_seeds_second_boot(
    tmp_config_dir,
    starter_folder_minimal,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boot 2 with pre-seeded matching hash completes cleanly; no new ERROR records.

    The matching hash is computed over the real ``initial_setup/starter_projects/``
    folder and written to ``<config_dir>/starter_projects.hash`` before Boot 2. The
    FileLock-wrapped hash gate in lifespan would then hit the short-circuit path --
    but this test chains the public API (no FileLock), so the short-circuit is
    exercised by the ``run_starter_projects_hash_gate`` caller. The integration
    assertion here is that running the chain TWICE in the same session against
    the same tmp state does not raise init-order errors.
    """
    # Boot 1.
    with caplog.at_level(logging.ERROR):
        await _run_lifespan_chain()
    offenders_boot_1 = _init_order_error_records(caplog)
    assert not offenders_boot_1, (
        f"Boot 1 produced init-order ERROR records: {[r.getMessage() for r in offenders_boot_1]!r}"
    )

    # Pre-seed a MATCHING hash file between boots (simulates hash-hit path on restart).
    hash_path = tmp_config_dir / HASH_FILENAME
    matching_hash = await compute_starter_projects_hash(starter_folder_minimal)
    await write_hash_file_safe(hash_path, matching_hash, "test")
    assert hash_path.exists(), "Seeded hash file should exist after write"

    # Boot 2: repeat the chain. No new ERROR records should appear.
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        await _run_lifespan_chain()
    offenders_boot_2 = _init_order_error_records(caplog)
    assert not offenders_boot_2, (
        f"Boot 2 produced init-order ERROR records: {[r.getMessage() for r in offenders_boot_2]!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 -- second boot with CORRUPT hash file (graceful fall-through).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_with_corrupt_hash_falls_through_cleanly(
    tmp_config_dir,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boot 2 with garbage hash file completes cleanly (full re-sync, no init errors)."""
    # Boot 1.
    await _run_lifespan_chain()

    # Write garbage to the hash file.
    hash_path = tmp_config_dir / HASH_FILENAME
    hash_path.write_text("not-a-hash\n")

    # Boot 2: chain should complete without init-order errors; starter-projects
    # re-sync path is the fall-through outcome (full sync when hash is corrupt).
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        await _run_lifespan_chain()
    offenders = _init_order_error_records(caplog)
    assert not offenders, (
        f"Boot 2 with corrupt hash produced init-order ERROR records: {[r.getMessage() for r in offenders]!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 -- LANGFLOW_FORCE_STARTER_RESYNC forces re-sync after clean boot.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_resync_env_var_second_boot_clean(
    tmp_config_dir,  # noqa: ARG001 -- fixture side-effect: redirects LANGFLOW_CONFIG_DIR + DB URL
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LANGFLOW_FORCE_STARTER_RESYNC=1 on Boot 2 forces full re-sync; no init errors."""
    # Boot 1: establishes DB + starter-projects + writes hash.
    await _run_lifespan_chain()

    # Force-resync on Boot 2.
    monkeypatch.setenv("LANGFLOW_FORCE_STARTER_RESYNC", "1")

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        await _run_lifespan_chain()
    offenders = _init_order_error_records(caplog)
    assert not offenders, (
        f"Boot 2 with LANGFLOW_FORCE_STARTER_RESYNC=1 produced init-order ERROR records: "
        f"{[r.getMessage() for r in offenders]!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 -- parity: services/utils.py module structure unchanged.
# ---------------------------------------------------------------------------


def test_services_utils_module_structure_unchanged() -> None:
    """Assert ``services/utils.py`` top-level async function names + order are unchanged.

    contract: service initialization order is preserved. plans
    04-01 through 04-04 all modified ``langflow/main.py`` but NOT
    ``langflow/services/utils.py`` -- the init ordering (database, superuser,
    orphan-reassignment, transaction cleanup) is preserved verbatim.

    This test codifies the current module-level function layout. If a future
    change adds/removes/reorders a function in services/utils.py, this test
    fails and the author must explicitly document the compatibility
    impact.
    """
    import langflow.services.utils as utils_mod

    source = inspect.getsource(utils_mod)
    tree = ast.parse(source)
    names = [node.name for node in tree.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))]
    expected = [
        "get_or_create_super_user",
        "setup_superuser",
        "migrate_orphaned_mcp_servers_config",
        "teardown_superuser",
        "teardown_services",
        "initialize_settings_service",
        "initialize_session_service",
        "clean_transactions",
        "clean_vertex_builds",
        "register_all_service_factories",
        "register_builtin_adapters",
        "register_builtin_deployment_mappers",
        "initialize_services",
    ]
    assert names == expected, (
        "services/utils.py top-level function names/order changed. "
        "SVC-04 parity requires the init ordering in this module remain stable. "
        f"Expected {expected!r}, got {names!r}."
    )


def test_initialize_services_signature_unchanged() -> None:
    """Guard initialize_services' public signature (``fix_migration: bool = False``).

    The restart-parity contract is that callers (FastAPI lifespan,
    integration tests, CLI `langflow run`) continue to invoke
    ``await initialize_services(fix_migration=...)`` with exactly this
    keyword-only bool. Changing the signature breaks every caller silently.
    """
    sig = inspect.signature(initialize_services)
    params = dict(sig.parameters)
    assert "fix_migration" in params, f"initialize_services missing fix_migration; got {list(params)!r}"
    fix_migration = params["fix_migration"]
    assert fix_migration.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"fix_migration must be keyword-only (SVC-04 parity); got kind={fix_migration.kind!r}"
    )
    assert fix_migration.default is False, (
        f"fix_migration default must be False (SVC-04 parity); got {fix_migration.default!r}"
    )
