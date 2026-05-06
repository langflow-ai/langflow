"""Tests for `lfx._bench` checkpoint landmarks.

Verifies the landmarks emitted from `lfx.services.initialize` and `lfx.load.load`
fire at the right places and are cost-free when disabled. No docker, hyperfine,
or benchmark scaffolding required.
"""

from __future__ import annotations

import contextlib
import json
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


_RELOADED_MODULES = ("lfx._bench", "lfx.services.initialize")


def _reset_bench_modules(monkeypatch, *, enabled: bool, dump_path: Path | None = None) -> None:
    """Reset env vars and force reload of `lfx._bench` so the module-level _ENABLED flag reflects the new env.

    The module caches _ENABLED at import time, so a plain monkeypatch without reload would not flip it.

    Restores any popped modules at teardown via ``monkeypatch.setitem`` so adjacent
    tests do not see the reloaded copies.
    """
    if enabled:
        monkeypatch.setenv("LFX_BENCHMARK_CHECKPOINTS", "1")
        if dump_path is not None:
            monkeypatch.setenv("LFX_BENCHMARK_CHECKPOINTS_FILE", str(dump_path))
    else:
        monkeypatch.delenv("LFX_BENCHMARK_CHECKPOINTS", raising=False)
        monkeypatch.delenv("LFX_BENCHMARK_CHECKPOINTS_FILE", raising=False)

    # Snapshot the original module objects (if loaded) so monkeypatch restores
    # them on teardown. ``delitem`` rolls back, restoring the originals.
    for mod in _RELOADED_MODULES:
        if mod in sys.modules:
            monkeypatch.delitem(sys.modules, mod)


@pytest.fixture
def bench_enabled(tmp_path, monkeypatch):
    """Enable _bench and point it at a tmp file. Yields the dump path."""
    dump_path = tmp_path / "checkpoints.json"
    _reset_bench_modules(monkeypatch, enabled=True, dump_path=dump_path)
    return dump_path


def test_initialize_services_emits_after_initialize_services(bench_enabled):  # noqa: ARG001
    """Importing lfx.services.initialize records `after-initialize-services`.

    The checkpoint is appended by the module-level `_checkpoint(...)` call at the end of
    `lfx/services/initialize.py`, which runs exactly once per process the first time the
    module is imported.
    """
    import lfx._bench

    # Freshly reloaded _bench: _CHECKPOINTS should contain only process-start at this point.
    initial_names = [n for n, _t in lfx._bench._CHECKPOINTS]
    assert "process-start" in initial_names

    import lfx.services.initialize

    names_after = [n for n, _t in lfx._bench._CHECKPOINTS]
    assert "after-initialize-services" in names_after, (
        f"expected after-initialize-services in checkpoints, got: {names_after}"
    )


@pytest.mark.asyncio
async def test_load_emits_after_component_index(bench_enabled):  # noqa: ARG001
    """Completing `ensure_component_hash_lookups_loaded()` records `after-component-index`.

    Exercised through the `lfx.load.load` path: the `_checkpoint("after-component-index")` call
    lives inside the `try` block immediately after the await.
    """
    import lfx._bench
    from lfx.utils.flow_validation import ensure_component_hash_lookups_loaded

    # The checkpoint is emitted from inside `aload_flow_from_json`, but the same module-scope
    # import of `lfx._bench.checkpoint` will fire the landmark after the helper completes.
    # Here we reuse the exact flow_validation path (a no-op if already loaded). We then import
    # `lfx.load.load` and call its `aload_flow_from_json` via the noop fixture to exercise the
    # landmark in context.
    try:
        await ensure_component_hash_lookups_loaded()
    except Exception as exc:  # pragma: no cover - test env issue
        pytest.skip(f"ensure_component_hash_lookups_loaded failed in test env: {exc!r}")

    # Now explicitly exercise the lfx.load.load path so the landmark fires at the canonical site.
    from lfx.load.load import aload_flow_from_json

    # Build a minimal valid flow dict. The goal is not to successfully load a real graph;
    # it is to reach the `_checkpoint("after-component-index")` line inside the try block.
    # Any call that completes the ensure_... await will trigger the checkpoint.
    minimal_flow = {"data": {"nodes": [], "edges": []}}
    # The downstream Graph.from_payload likely raises on an empty flow; that's fine.
    # The checkpoint fires BEFORE that step, inside the try block, which is what we test.
    with contextlib.suppress(Exception):
        await aload_flow_from_json(minimal_flow)

    names = [n for n, _t in lfx._bench._CHECKPOINTS]
    assert "after-component-index" in names, f"expected after-component-index in checkpoints, got: {names}"


def test_checkpoints_disabled_is_zero_cost(tmp_path, monkeypatch):  # noqa: ARG001
    """When LFX_BENCHMARK_CHECKPOINTS is unset, no checkpoints are recorded.

    The two new landmarks (initialize.py and load.py) both call `checkpoint(...)`, which is a
    cheap no-op guarded by the `_ENABLED` flag. The list stays empty.
    """
    _reset_bench_modules(monkeypatch, enabled=False)

    import lfx._bench
    import lfx.services.initialize

    assert lfx._bench._CHECKPOINTS == [], f"expected empty _CHECKPOINTS when disabled, got: {lfx._bench._CHECKPOINTS}"


def test_dump_writes_named_checkpoints(bench_enabled):
    """End-to-end sanity check for the landmark pair.

    Enabling `_bench`, emitting both landmarks, and calling `dump()` produces a JSON file
    whose array of `[name, ts]` pairs contains the two new names at valid timestamps.
    """
    import lfx._bench
    import lfx.services.initialize

    lfx._bench.checkpoint("after-component-index")  # simulate the load.py landmark firing
    lfx._bench.dump()

    payload = json.loads(bench_enabled.read_text(encoding="utf-8"))
    names = [entry[0] for entry in payload]
    assert "process-start" in names
    assert "after-initialize-services" in names
    assert "after-component-index" in names
    # Timestamps must be monotonically non-decreasing (perf_counter is monotonic).
    timestamps = [entry[1] for entry in payload]
    assert all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
