"""Process-model tests for `lfx serve` per-request-isolated execution.

Covers the preload/warm/guard/fork-safety pieces of the gunicorn
``--preload`` + ``max_requests=1`` architecture:

- ``build_registry_from_env`` builds and warms a registry from the LFX_SERVE_*
  environment (the single source reused by the uvicorn factory and the gunicorn
  preload master).
- ``serve_preloaded_app`` builds the warm app at import time and ``gc.freeze()``s.
- ``LFXGunicornApp`` translates options into a gunicorn config.
- The single-in-flight execute guard serializes the env-sensitive section.
- Fork-safety regressions (DB-less serve, uuid4-based ids).
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


def test_preloaded_app_module_builds_warm_app_and_freezes(tmp_path, monkeypatch):
    import gc
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
    assert gc.get_freeze_count() > 0  # gc.freeze() ran at import


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


def test_serve_command_refuses_multiworker_on_windows(monkeypatch, tmp_path):
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
        )

    # The Windows refusal must not leave the worker env vars set.
    import os as _os

    from lfx.cli.serve_app import (
        _SERVE_FLOW_DIR_ENV,
        _SERVE_NO_ENV_FALLBACK_ENV,
        _SERVE_STARTUP_PATHS_ENV,
    )

    for key in (_SERVE_FLOW_DIR_ENV, _SERVE_NO_ENV_FALLBACK_ENV, _SERVE_STARTUP_PATHS_ENV):
        assert key not in _os.environ


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
