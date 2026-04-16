"""Cold-start benchmark checkpoint hook (MEAS-03).

Stdlib-only by design: `lfx` has no runtime deps, and this module ships with
`lfx`. Gated on the `LFX_BENCHMARK_CHECKPOINTS` env var. When unset, every
function in this module is effectively a no-op (one dict lookup + early return).

When set, records `time.perf_counter()` timestamps at named checkpoints and
dumps them as JSON to `LFX_BENCHMARK_CHECKPOINTS_FILE` (default
`/tmp/lfx_checkpoints.json`). The harness driver (see
`src/backend/tests/benchmarks/driver.py`, plan 05) reads that file and renders
the per-phase breakdown.

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

_ENABLED: bool = bool(os.environ.get("LFX_BENCHMARK_CHECKPOINTS"))
_DEFAULT_FILE: str = "/tmp/lfx_checkpoints.json"  # noqa: S108
_CHECKPOINTS: list[tuple[str, float]] = []

if _ENABLED:
    # Record process-start AT MODULE IMPORT TIME. This is the earliest we can
    # reasonably place this checkpoint. `lfx/cli/run.py` imports `_bench` before
    # any other lfx module (so we capture the interpreter's own startup cost
    # to the degree Python lets us observe it).
    _CHECKPOINTS.append(("process-start", time.perf_counter()))


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
    os.replace(tmp, target)
