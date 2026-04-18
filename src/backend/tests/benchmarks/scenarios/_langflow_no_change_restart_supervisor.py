"""Supervisor: SVC-01 no-change-restart benchmark.

Two modes, both driven by CLI flags:

  --prewarm: boot ``langflow run`` once, wait for ``Application startup complete.``
    on stderr, then SIGTERM. Writes ``<state>/starter_projects.hash`` and populates
    the shared SQLite DB under ``<state>/bench.db`` so the measured boot can hit
    the SVC-01 hash-match short-circuit. Used via hyperfine ``--setup`` so it runs
    exactly once per benchmark invocation, not once per iteration.

  --measure (default): boot ``langflow run`` once against the pre-populated state
    dir and return. hyperfine measures this boot's wall-clock; with the hash gate
    firing, the lifespan exits in milliseconds on the starter-project block and
    the MCP Event fires near-immediately.

Shared state:
  Both modes read the state directory from ``$BENCH_STATE_DIR`` (set by the driver
  via a bind mount at ``/bench-state``). If unset, we fall back to a deterministic
  tmp directory so the supervisor is self-contained for local ad-hoc runs. The
  supervisor exports ``LANGFLOW_CONFIG_DIR`` and ``LANGFLOW_DATABASE_URL`` into
  the environment so the subprocess sees them.

Exit codes:
  0 - success (marker observed; in measure mode the benchmark was captured).
  2 - timeout (STARTUP_TIMEOUT_SEC elapsed without the marker).
  3 - early exit (process exited before the marker appeared).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

READY_MARKER = "Application startup complete."
# 60s is sufficient on Linux CI (typical cold boot is 30-40s). macOS/podman runs with an
# emulated VM need more headroom; ``LANGFLOW_BENCH_STARTUP_TIMEOUT`` overrides at
# invocation time. Apply the same generous ceiling to both modes for predictability.
STARTUP_TIMEOUT_SEC = float(os.environ.get("LANGFLOW_BENCH_STARTUP_TIMEOUT", "180"))


def _langflow_argv() -> list[str]:
    """Return the ``langflow run`` command used for both modes."""
    return [
        "uv",
        "run",
        "langflow",
        "run",
        "--backend-only",
        "--host",
        "127.0.0.1",
        "--port",
        "7860",
        "--no-open-browser",
    ]


def _ensure_state_env() -> Path:
    """Resolve (and export) the shared state directory; return its Path."""
    state_root = os.environ.get("BENCH_STATE_DIR")
    if not state_root:
        state_root = str(Path(tempfile.gettempdir()) / "langflow_bench_no_change_restart")
    state_path = Path(state_root)
    state_path.mkdir(parents=True, exist_ok=True)
    os.environ["LANGFLOW_CONFIG_DIR"] = str(state_path)
    os.environ.setdefault(
        "LANGFLOW_DATABASE_URL",
        f"sqlite:///{state_path / 'bench.db'}",
    )
    return state_path


def _boot_once(*, measure: bool) -> float | None:
    """Launch ``langflow run``, wait for ready marker, SIGTERM, return elapsed ms (or None).

    When ``measure`` is False the elapsed ms is discarded; the return value is 0.0 on
    success and ``None`` on failure (callers distinguish via the process exit code
    they propagate to the outer driver).
    """
    start = time.perf_counter()
    proc = subprocess.Popen(  # noqa: S603
        _langflow_argv(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        sys.stderr.write("ERROR: Popen did not provide a stdout stream\n")
        return None

    ready_at: float | None = None
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if READY_MARKER in line:
                ready_at = time.perf_counter()
                break
            if time.perf_counter() - start > STARTUP_TIMEOUT_SEC:
                sys.stderr.write(f"TIMEOUT: {STARTUP_TIMEOUT_SEC}s elapsed without seeing {READY_MARKER!r}\n")
                proc.terminate()
                return None
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    if ready_at is None:
        sys.stderr.write("ERROR: process exited before ready marker appeared\n")
        return None

    if not measure:
        return 0.0
    return (ready_at - start) * 1000.0


def _run_prewarm(state_path: Path) -> int:
    """Boot once to populate ``state_path``. Returns process exit code."""
    sys.stdout.write(f"=== PREWARM (state={state_path}) ===\n")
    sys.stdout.flush()
    if _boot_once(measure=False) is None:
        return 3
    hash_file = state_path / "starter_projects.hash"
    if not hash_file.exists():
        sys.stderr.write(f"WARNING: pre-warm did not produce {hash_file}\n")
    return 0


def _run_measure(state_path: Path) -> int:
    """Single measured boot against pre-warmed state. Returns process exit code."""
    sys.stdout.write(f"=== MEASURE (state={state_path}) ===\n")
    sys.stdout.flush()
    boot_ms = _boot_once(measure=True)
    if boot_ms is None:
        return 3
    sys.stdout.write(f"LANGFLOW_NO_CHANGE_RESTART_MS={boot_ms:.2f}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint with two modes."""
    parser = argparse.ArgumentParser(
        description="SVC-01 no-change-restart benchmark supervisor",
        allow_abbrev=False,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--prewarm",
        action="store_const",
        dest="mode",
        const="prewarm",
        help="Run Boot 1 only to populate the shared state dir, then exit.",
    )
    group.add_argument(
        "--measure",
        action="store_const",
        dest="mode",
        const="measure",
        help="Run a single measured boot against the pre-warmed state.",
    )
    args = parser.parse_args(argv)
    # Default to measure so hyperfine's main command can omit the flag if desired.
    mode = args.mode or "measure"

    state_path = _ensure_state_env()
    if mode == "prewarm":
        return _run_prewarm(state_path)
    return _run_measure(state_path)


if __name__ == "__main__":
    raise SystemExit(main())
