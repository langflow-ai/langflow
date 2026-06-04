"""Process-model tests for `lfx serve` per-request-isolated execution.

Covers the preload/warm/guard/fork-safety pieces of the gunicorn
``--preload`` + ``max_requests=1`` architecture:

- ``build_registry_from_env`` builds and warms a registry from the LFX_SERVE_*
  environment (the single source reused by the uvicorn factory and the gunicorn
  preload master).
- ``serve_preloaded_app`` builds the warm app at import time (freezing happens in
  the gunicorn ``pre_fork`` hook, not at import).
- ``LFXGunicornApp`` translates options into a gunicorn config and runs the
  ``pre_fork`` fork-safety hook (gc.freeze + ghost-thread/connection diagnostics).
- The single-in-flight execute guard serializes the env-sensitive section.
- Fork-safety regressions: DB-less serve, uuid4-based ids, preload must not open
  the DB or start background threads, and the pre_fork guardrail must fire.
"""

import json
import sys
from pathlib import Path

import pytest


def _write_flow(flow_dir: Path, flow_id: str) -> None:
    """Write a minimal empty-graph flow JSON into *flow_dir* as ``{flow_id}.json``.

    An empty graph (no nodes/edges) reconstructs via ``load_flow_from_json`` +
    ``graph.prepare()`` without requiring the component-type cache to be
    initialised, so warming exercises the real ``FilesystemFlowStore`` round-trip
    without external setup. This mirrors the reconstructable fixtures used by the
    existing serve tests.
    """
    raw = {
        "name": flow_id,
        "description": None,
        "id": flow_id,
        "data": {"nodes": [], "edges": []},
    }
    (flow_dir / f"{flow_id}.json").write_text(json.dumps(raw), encoding="utf-8")


def test_build_registry_from_env_warms_store(tmp_path, monkeypatch):
    from lfx.cli import serve_app

    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    _write_flow(flow_dir, "flow-1")
    monkeypatch.setenv(serve_app._SERVE_FLOW_DIR_ENV, str(flow_dir))
    monkeypatch.setenv(serve_app._SERVE_NO_ENV_FALLBACK_ENV, "1")
    monkeypatch.setenv(serve_app._SERVE_STARTUP_PATHS_ENV, "")

    registry = serve_app.build_registry_from_env()

    assert registry.get("flow-1") is not None  # warm, not lazy
    assert registry._no_env_fallback is True


def test_preloaded_app_module_builds_warm_app(tmp_path, monkeypatch):
    import importlib

    from fastapi import FastAPI
    from lfx.cli import serve_app

    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    _write_flow(flow_dir, "flow-1")
    monkeypatch.setenv(serve_app._SERVE_FLOW_DIR_ENV, str(flow_dir))
    monkeypatch.setenv(serve_app._SERVE_NO_ENV_FALLBACK_ENV, "0")
    monkeypatch.setenv(serve_app._SERVE_STARTUP_PATHS_ENV, "")

    import lfx.cli.serve_preloaded_app as mod

    importlib.reload(mod)  # re-run import-time build under patched env

    assert isinstance(mod.app, FastAPI)
    assert mod.registry.get("flow-1") is not None
    # The module does NOT freeze at import; freezing happens in the gunicorn
    # pre_fork hook (see test_gunicorn_pre_fork_freezes_heap).


@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn is Unix-only")
def test_gunicorn_pre_fork_freezes_heap_and_runs_clean(monkeypatch):
    """The pre_fork hook calls gc.freeze() (preserving COW) and runs without raising.

    Spies on gc.freeze directly rather than gc.get_freeze_count(): the hook also
    calls gc.collect(), which by itself bumps the freeze count, so a count-based
    assertion would pass even if gc.freeze() were removed.
    """
    import gc
    from unittest.mock import MagicMock

    from lfx.cli.serve_gunicorn import LFXGunicornApp

    class _FakeLog:
        def warning(self, *_a, **_k):
            pass

        def debug(self, *_a, **_k):
            pass

    class _FakeServer:
        log = _FakeLog()

    freeze_spy = MagicMock()
    monkeypatch.setattr(gc, "freeze", freeze_spy)

    LFXGunicornApp.pre_fork(_FakeServer(), None)

    freeze_spy.assert_called_once()  # gc.freeze() ran in the hook


@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn is Unix-only")
def test_gunicorn_app_registers_pre_fork_hook():
    from lfx.cli.serve_gunicorn import LFXGunicornApp

    gapp = LFXGunicornApp("lfx.cli.serve_preloaded_app:app", {"workers": 2})
    gapp.load_config()
    # The pre_fork hook is wired into gunicorn's config so it runs before each fork.
    # (Bound classmethods aren't identity-equal across accesses; compare the function.
    # getattr default keeps this a clean assertion failure if the hook isn't wired,
    # since gunicorn's default pre_fork is a plain function with no __func__.)
    assert getattr(gapp.cfg.pre_fork, "__func__", None) is LFXGunicornApp.pre_fork.__func__


@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn is Unix-only")
def test_gunicorn_app_sets_options():
    from lfx.cli.serve_gunicorn import LFXGunicornApp

    opts = {
        "bind": "127.0.0.1:7860",
        "workers": 4,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "preload_app": True,
        "max_requests": 1,
        "max_requests_jitter": 0,
        "loglevel": "info",
    }
    gapp = LFXGunicornApp("lfx.cli.serve_preloaded_app:app", opts)
    gapp.load_config()
    assert gapp.cfg.workers == 4
    assert gapp.cfg.max_requests == 1
    assert gapp.cfg.preload_app is True
    # gunicorn resolves worker_class to the loaded class; the original import
    # string is preserved on worker_class_str.
    assert gapp.cfg.worker_class_str == "uvicorn.workers.UvicornWorker"


def _assert_worker_env_cleaned():
    import os as _os

    from lfx.cli.serve_app import (
        _SERVE_FLOW_DIR_ENV,
        _SERVE_NO_ENV_FALLBACK_ENV,
        _SERVE_STARTUP_PATHS_ENV,
    )

    for key in (_SERVE_FLOW_DIR_ENV, _SERVE_NO_ENV_FALLBACK_ENV, _SERVE_STARTUP_PATHS_ENV):
        assert key not in _os.environ


def test_windows_multiworker_default_falls_back_to_uvicorn(monkeypatch, tmp_path):
    """On Windows with no --max-requests, multi-worker falls back to uvicorn (no isolation)."""
    from lfx.cli import commands

    monkeypatch.setattr(commands.sys, "platform", "win32")

    called = {}

    def fake_uvicorn_run(app_str, **kwargs):
        called["app"] = app_str
        called["kwargs"] = kwargs

    monkeypatch.setattr(commands.uvicorn, "run", fake_uvicorn_run)

    commands._launch_workers(
        host="127.0.0.1",
        port=8000,
        workers=2,
        log_level="warning",
        flow_dir=tmp_path,
        no_env_fallback=False,
        script_paths=None,
        temp_file_to_cleanup=None,
        verbose_print=lambda *_a, **_k: None,
        max_requests=None,
        limit_concurrency=1,
    )

    # Falls back to the uvicorn factory multi-worker path, not gunicorn.
    assert called["app"] == "lfx.cli.serve_app:create_serve_app"
    assert called["kwargs"].get("workers") == 2
    assert called["kwargs"].get("factory") is True
    # --limit-concurrency is honored on Windows (uvicorn-native); +1 because uvicorn
    # counts the active connection, so "1 in-flight" maps to uvicorn's 2.
    assert called["kwargs"].get("limit_concurrency") == 2
    _assert_worker_env_cleaned()


def test_windows_multiworker_with_max_requests_errors(monkeypatch, tmp_path):
    """On Windows, requesting isolation via --max-requests is refused (gunicorn unavailable)."""
    import typer
    from lfx.cli import commands

    monkeypatch.setattr(commands.sys, "platform", "win32")

    with pytest.raises(typer.Exit):
        commands._launch_workers(
            host="127.0.0.1",
            port=8000,
            workers=2,
            log_level="warning",
            flow_dir=tmp_path,
            no_env_fallback=False,
            script_paths=None,
            temp_file_to_cleanup=None,
            verbose_print=lambda *_a, **_k: None,
            max_requests=1,
            limit_concurrency=None,
        )

    _assert_worker_env_cleaned()


def test_lfx_uvicorn_worker_applies_limit_concurrency(monkeypatch):
    """LFXUvicornWorker reads LFX_SERVE_LIMIT_CONCURRENCY and sets it on the uvicorn config.

    Tested via the static helper so we don't have to construct a full gunicorn worker.
    """
    from types import SimpleNamespace

    from lfx.cli.serve_app import _SERVE_LIMIT_CONCURRENCY_ENV
    from lfx.cli.serve_gunicorn import LFXUvicornWorker

    cfg = SimpleNamespace(limit_concurrency=None)
    monkeypatch.setenv(_SERVE_LIMIT_CONCURRENCY_ENV, "1")
    LFXUvicornWorker._apply_limit_concurrency(cfg)
    # +1: uvicorn counts the active connection, so "1 in-flight" maps to uvicorn's 2
    # (uvicorn's limit_concurrency=1 would reject every request).
    assert cfg.limit_concurrency == 2

    # Unset -> left at the uvicorn default (None), i.e. unlimited.
    cfg2 = SimpleNamespace(limit_concurrency=None)
    monkeypatch.delenv(_SERVE_LIMIT_CONCURRENCY_ENV, raising=False)
    LFXUvicornWorker._apply_limit_concurrency(cfg2)
    assert cfg2.limit_concurrency is None


async def test_guarded_execute_serializes(monkeypatch):
    import asyncio

    from lfx.cli import serve_app

    timeline = []

    async def fake_capture(graph, input_value, session_id=None):  # noqa: ARG001
        timeline.append(("enter", input_value))
        await asyncio.sleep(0.05)
        timeline.append(("exit", input_value))
        return ([], "")

    monkeypatch.setattr(serve_app, "execute_graph_with_capture", fake_capture)

    await asyncio.gather(
        serve_app.guarded_execute(object(), "a", None),
        serve_app.guarded_execute(object(), "b", None),
    )

    # No interleave: each enter is immediately followed by its own exit.
    assert timeline in (
        [("enter", "a"), ("exit", "a"), ("enter", "b"), ("exit", "b")],
        [("enter", "b"), ("exit", "b"), ("enter", "a"), ("exit", "a")],
    )


def test_upload_visible_to_fresh_worker(tmp_path, monkeypatch):
    """Upload via one registry must be reconstructable by a freshly forked worker.

    The fresh worker builds its registry from the same shared store. This is the
    multi-worker upload contract under per-request recycling: the
    uploading worker persists raw_json to the FilesystemFlowStore; any later
    worker rebuilds the graph from the store on a cache miss.
    """
    from lfx.cli import serve_app
    from lfx.cli.flow_store import FilesystemFlowStore
    from lfx.load import load_flow_from_json

    store_dir = tmp_path / "store"
    store_dir.mkdir()

    raw = {"name": "uploaded", "id": "uploaded-1", "data": {"nodes": [], "edges": []}}

    # Registry A "uploads" the flow: registry.add persists raw_json to the store.
    registry_a = serve_app.FlowRegistry(store=FilesystemFlowStore(store_dir))
    graph_a = load_flow_from_json(raw)
    graph_a.prepare()
    meta_a = serve_app.FlowMeta(id="uploaded-1", relative_path="<upload>", title="uploaded", description=None)
    registry_a.add(graph_a, meta_a, raw_json=raw)

    # Registry B simulates a freshly forked worker: build from the same store via env.
    monkeypatch.setenv(serve_app._SERVE_FLOW_DIR_ENV, str(store_dir))
    monkeypatch.setenv(serve_app._SERVE_NO_ENV_FALLBACK_ENV, "0")
    monkeypatch.setenv(serve_app._SERVE_STARTUP_PATHS_ENV, "")
    registry_b = serve_app.build_registry_from_env()

    assert registry_b.get("uploaded-1") is not None


def test_serve_context_is_db_less():
    """`lfx serve` is DB-less: get_db_service() returns a NoopDatabaseService.

    Guards against a future change that would make per-fork DB connection reinit
    necessary (preload + fork would then need a post-fork pool reset).
    """
    from lfx.services.database.service import NoopDatabaseService
    from lfx.services.deps import get_db_service

    assert isinstance(get_db_service(), NoopDatabaseService)


def test_uuid4_is_unique_and_fork_safe():
    """uuid4 (os.urandom-backed) is fork-safe and collision-free for flow ids.

    A forked worker must not reproduce the parent's RNG stream. uuid4 draws from
    os.urandom, which is re-seeded per process, so generated ids stay unique.
    """
    import uuid

    ids = {str(uuid.uuid4()) for _ in range(10_000)}
    assert len(ids) == 10_000


def _build_preloaded(monkeypatch, tmp_path):
    """Run the exact work the gunicorn preload master does: build + warm the app."""
    from lfx.cli import serve_app

    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    _write_flow(flow_dir, "flow-1")
    monkeypatch.setenv(serve_app._SERVE_FLOW_DIR_ENV, str(flow_dir))
    monkeypatch.setenv(serve_app._SERVE_NO_ENV_FALLBACK_ENV, "0")
    monkeypatch.setenv(serve_app._SERVE_STARTUP_PATHS_ENV, "")
    registry = serve_app.build_registry_from_env()
    return serve_app.create_multi_serve_app(registry=registry)


def test_preload_does_not_open_the_database(tmp_path, monkeypatch):
    """Fork-safety invariant: building/warming the preload app must NOT open a DB session.

    This is the property that keeps lfx serve fork-safe with a pluggable DB: if the
    preload master opened a session, an eager-engine DB service would create its
    connection pool pre-fork and every forked worker would inherit/corrupt it. A
    spy on get_db_service() catches all DB access (session_scope resolves it at
    call-time), so this fails loudly if any future preload step touches the DB.
    """
    from contextlib import asynccontextmanager

    from lfx.services import deps

    opened = {"count": 0}

    class _SpyDB:
        @asynccontextmanager
        async def _with_session(self):
            opened["count"] += 1
            from lfx.services.session import NoopSession

            async with NoopSession() as session:
                yield session

    monkeypatch.setattr(deps, "get_db_service", lambda: _SpyDB())

    _build_preloaded(monkeypatch, tmp_path)

    assert opened["count"] == 0, "preload opened a DB session — fork-unsafe with a real DB service"


def test_preload_starts_no_fork_unsafe_background_threads(tmp_path, monkeypatch):
    """Fork-safety invariant: building the preload app must not leave non-benign threads.

    Background threads (telemetry, threaded logging, schedulers) are NOT inherited
    by forks, so any started during preload would silently die in workers — and one
    holding a lock at fork could deadlock the child.
    """
    import threading

    from lfx.cli.serve_gunicorn import LFXGunicornApp

    before = {t.ident for t in threading.enumerate()}
    _build_preloaded(monkeypatch, tmp_path)
    new_alive = [t for t in threading.enumerate() if t.ident not in before and t.is_alive()]
    suspicious = [t for t in new_alive if not LFXGunicornApp._is_benign_thread(t)]

    assert not suspicious, f"preload started fork-unsafe background threads: {[t.name for t in suspicious]}"


@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn is Unix-only")
def test_pre_fork_flags_ghost_thread_but_not_benign():
    """The pre_fork guardrail must warn about a non-benign thread alive before fork
    and must NOT flag a benign-named one.
    """
    import threading

    from lfx.cli.serve_gunicorn import LFXGunicornApp

    warnings: list[str] = []

    class _Log:
        def warning(self, msg, *args):
            warnings.append(msg % args if args else msg)

        def debug(self, *_a, **_k):
            pass

    class _Server:
        log = _Log()

    stop = threading.Event()
    ghost = threading.Thread(target=stop.wait, name="EvilGhostThread", daemon=True)
    benign = threading.Thread(target=stop.wait, name="OTel-benign", daemon=True)
    ghost.start()
    benign.start()
    try:
        LFXGunicornApp.pre_fork(_Server(), None)
    finally:
        stop.set()
        ghost.join(timeout=2)
        benign.join(timeout=2)

    blob = "\n".join(warnings)
    assert "Ghost threads" in blob and "EvilGhostThread" in blob, warnings
    assert "OTel-benign" not in blob  # benign-named threads are filtered out
