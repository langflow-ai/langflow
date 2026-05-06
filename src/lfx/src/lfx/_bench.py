"""Cold-start benchmark checkpoint hook.

Stdlib-only by design: `lfx` has no runtime deps, and this module ships with
`lfx`. Gated on the `LFX_BENCHMARK_CHECKPOINTS` env var. When unset, every
function in this module is effectively a no-op (one dict lookup + early return).

When set, records `time.perf_counter()` timestamps at named checkpoints and
dumps them as JSON to `LFX_BENCHMARK_CHECKPOINTS_FILE` (default
`/tmp/lfx_checkpoints.json`). The harness driver at
`src/backend/tests/benchmarks/driver.py` reads that file and renders the
per-phase breakdown.

The `process-start` checkpoint is recorded at MODULE IMPORT time. This is as
close to "Python interpreter has just started running user code" as we can
practically get. Subsequent checkpoints are recorded by explicit calls from
`lfx/cli/run.py`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

__all__ = ["checkpoint", "dump"]

_ENABLED: bool = os.environ.get("LFX_BENCHMARK_CHECKPOINTS", "").strip().lower() in {"1", "true", "yes", "on"}
_DEFAULT_FILE: str = "/tmp/lfx_checkpoints.json"  # noqa: S108
_CHECKPOINTS: list[tuple[str, float]] = []

if _ENABLED:
    # Record process-start AT MODULE IMPORT TIME. This is the earliest we can
    # reasonably place this checkpoint. `lfx/cli/run.py` imports `_bench` before
    # any other lfx module (so we capture the interpreter's own startup cost
    # to the degree Python lets us observe it).
    _CHECKPOINTS.append(("process-start", time.perf_counter()))

    # Optional bootstrap hook. The benchmark harness uses JSON fixtures, which do
    # NOT execute any fixture-level Python (e.g., mock-LLM installation). To let
    # callers hook module-level initialization (mocks, tracing shims, etc.) on
    # top of `lfx run <fixture>.json`, we honor two env vars:
    #   - LFX_BENCHMARK_BOOTSTRAP_MODULE: dotted import path (e.g. "pkg.mod").
    #   - LFX_BENCHMARK_BOOTSTRAP_PATH: absolute filesystem path to a .py file.
    # Stdlib-only, gated on the benchmark env vars, zero cost when unset. This
    # is a generic hook; `lfx` does NOT import any specific bootstrap module by
    # name. The path form is preferred when the bootstrap module lives in a
    # package that is not on sys.path or whose dotted name collides with a
    # third-party package (common with "tests" in site-packages).
    _bootstrap_mod = os.environ.get("LFX_BENCHMARK_BOOTSTRAP_MODULE")
    _bootstrap_path = os.environ.get("LFX_BENCHMARK_BOOTSTRAP_PATH")
    if _bootstrap_mod or _bootstrap_path:
        try:
            import importlib

            if _bootstrap_path:
                import importlib.util

                _spec = importlib.util.spec_from_file_location("_lfx_bench_bootstrap", _bootstrap_path)
                if _spec is None or _spec.loader is None:
                    msg = f"cannot build import spec from {_bootstrap_path!r}"
                    raise ImportError(msg)
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
            else:
                importlib.import_module(_bootstrap_mod)
        except Exception as _exc:  # noqa: BLE001
            # Do not let a broken bootstrap crash the benchmarked process; the driver
            # detects missing mocks downstream (401 error, etc.). Surface on stderr.
            import sys as _sys

            _which = _bootstrap_path or _bootstrap_mod
            _sys.stderr.write(f"LFX_BENCHMARK_BOOTSTRAP={_which!r} import failed: {_exc!r}\n")


def checkpoint(name: str) -> None:
    """Record a named checkpoint. No-op when LFX_BENCHMARK_CHECKPOINTS is unset.

    Cost when disabled: one global-read, one truthiness check, return. Well
    under 1us per call. Acceptable even on the hot import path.
    """
    if _ENABLED:
        _CHECKPOINTS.append((name, time.perf_counter()))


def dump() -> None:
    """Flush recorded checkpoints to disk.

    Path: `$LFX_BENCHMARK_CHECKPOINTS_FILE` if set, else `/tmp/lfx_checkpoints.json`.
    The file is written atomically via `os.replace` to survive concurrent dump
    calls (defensive; in practice there is only one per run). No-op when
    LFX_BENCHMARK_CHECKPOINTS is unset.

    Format: JSON array of `[name, perf_counter_seconds]` pairs, in the order
    checkpoint() was called.
    """
    if not _ENABLED:
        return

    target = Path(os.environ.get("LFX_BENCHMARK_CHECKPOINTS_FILE", _DEFAULT_FILE))
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = json.dumps([[name, ts] for name, ts in _CHECKPOINTS])
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(target)
