"""Supervisor: SVC-01 no-change-restart benchmark.

Self-contained benchmark harness. Unlike scenarios that run under ``hyperfine``,
this one is measured by the supervisor itself so progress is visible in CI logs
and so the measurement loop can share a state directory across iterations
without paying the docker cold-start penalty five times.

Three CLI modes:

  --prewarm: boot ``langflow run`` once, wait for ``Application startup complete.``
    on stderr, then SIGTERM. Writes ``<state>/starter_projects.hash`` and populates
    the shared SQLite DB so the measured boots hit the SVC-01 hash-match path.

  --measure: boot ``langflow run`` once against a pre-populated state dir and print
    the wall-clock milliseconds between process start and the ready marker.

  --bench N: run pre-warm once, then loop N measured boots, then write a
    hyperfine-compatible JSON report to ``$BENCH_OUTPUT_JSON`` (or
    ``reports/langflow_run_no_change_restart.json`` inside ``BENCH_STATE_DIR``
    when the env var is unset). Each iteration's wall-clock is logged.

Shared state:
  All modes read the state directory from ``$BENCH_STATE_DIR`` (set by the
  driver via a bind mount at ``/bench-state``). If unset, we fall back to a
  deterministic tmp directory so the supervisor is self-contained for local
  ad-hoc runs. The supervisor exports ``LANGFLOW_CONFIG_DIR`` and
  ``LANGFLOW_DATABASE_URL`` so the subprocess sees them.

Exit codes:
  0 - success.
  2 - timeout (STARTUP_TIMEOUT_SEC elapsed without the marker).
  3 - early exit (process exited before the marker appeared).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# We probe TCP readiness on 127.0.0.1:READY_PORT instead of scraping a stdout marker.
# The ``Application startup complete.`` log line that uvicorn emits is swallowed by
# langflow's structlog processor pipeline, so relying on it races under load (same
# class of failure the langflow_run_http_ready scenario hits). TCP connect success
# is a ground-truth readiness signal that does not depend on logging at all.
READY_HOST = "127.0.0.1"
READY_PORT = 7860
# Poll interval for TCP readiness probes. Short enough to keep measurement noise
# bounded; long enough to avoid trivial CPU burn during the ~30-40s cold boot.
READY_POLL_INTERVAL_SEC = 0.05
# 60s is sufficient on Linux CI (typical cold boot is 30-40s). macOS/podman runs with an
# emulated VM need more headroom; ``LANGFLOW_BENCH_STARTUP_TIMEOUT`` overrides at
# invocation time. Apply the same generous ceiling to every boot for predictability.
STARTUP_TIMEOUT_SEC = float(os.environ.get("LANGFLOW_BENCH_STARTUP_TIMEOUT", "180"))


def _langflow_argv() -> list[str]:
    """Return the ``langflow run`` command used for every boot."""
    return [
        "uv",
        "run",
        "langflow",
        "run",
        "--backend-only",
        "--host",
        READY_HOST,
        "--port",
        str(READY_PORT),
        "--no-open-browser",
    ]


def _drain_output(stream, stop_event: threading.Event) -> None:
    """Forward a subprocess pipe to stdout so CI logs show boot progress.

    Runs in a background thread so the main thread can poll TCP readiness without
    blocking on ``readline``. When ``stop_event`` fires we stop reading even if the
    child process is still producing output (the shutdown path doesn't care about
    lossless capture — it only cares about not deadlocking the parent).
    """
    try:
        for line in stream:
            if stop_event.is_set():
                break
            sys.stdout.write(line)
            sys.stdout.flush()
    except (ValueError, OSError):
        # Stream closed from under us; that's fine during shutdown.
        return


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


def _tcp_ready(host: str, port: int, *, connect_timeout: float = 0.5) -> bool:
    """Return True if a TCP connection to ``(host, port)`` succeeds within the deadline."""
    try:
        with socket.create_connection((host, port), timeout=connect_timeout):
            return True
    except OSError:
        return False


def _boot_once(*, measure: bool) -> float | None:
    """Launch ``langflow run``, poll TCP 127.0.0.1:7860 for readiness, SIGTERM, return ms.

    When ``measure`` is False the elapsed ms is discarded and the return value is 0.0
    on success. On failure (timeout or early exit) the return value is ``None``.

    Readiness is signalled by a successful TCP connect to the bind address. The
    supervisor tolerates a silent structlog pipeline because it never depends on
    log output to know when the server is up.
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

    stop_reader = threading.Event()
    reader = threading.Thread(
        target=_drain_output,
        args=(proc.stdout, stop_reader),
        daemon=True,
    )
    reader.start()

    ready_at: float | None = None
    try:
        while True:
            if _tcp_ready(READY_HOST, READY_PORT):
                ready_at = time.perf_counter()
                break
            if proc.poll() is not None:
                sys.stderr.write(
                    f"ERROR: process exited (rc={proc.returncode}) before {READY_HOST}:{READY_PORT} was ready\n",
                )
                return None
            if time.perf_counter() - start > STARTUP_TIMEOUT_SEC:
                sys.stderr.write(
                    f"TIMEOUT: {STARTUP_TIMEOUT_SEC}s elapsed without "
                    f"{READY_HOST}:{READY_PORT} accepting connections\n",
                )
                return None
            time.sleep(READY_POLL_INTERVAL_SEC)
    finally:
        stop_reader.set()
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        reader.join(timeout=2)

    if ready_at is None:
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


def _write_hyperfine_report(path: Path, *, command: str, samples_ms: list[float]) -> None:
    """Write a hyperfine --export-json compatible report."""
    samples_s = [m / 1000.0 for m in samples_ms]
    mean_s = statistics.fmean(samples_s) if samples_s else 0.0
    stddev_s = statistics.pstdev(samples_s) if len(samples_s) >= 2 else 0.0
    median_s = statistics.median(samples_s) if samples_s else 0.0
    min_s = min(samples_s) if samples_s else 0.0
    max_s = max(samples_s) if samples_s else 0.0
    payload = {
        "results": [
            {
                "command": command,
                "mean": mean_s,
                "stddev": stddev_s,
                "median": median_s,
                "min": min_s,
                "max": max_s,
                "times": samples_s,
                "exit_codes": [0] * len(samples_s),
                "parameters": {},
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_bench(state_path: Path, *, iterations: int) -> int:
    """Pre-warm once, then measure ``iterations`` boots and write a hyperfine-format report.

    Output path resolution:
      * ``$BENCH_OUTPUT_JSON`` if set
      * else ``<state_path>/langflow_run_no_change_restart.json``
    """
    if iterations < 1:
        sys.stderr.write(f"ERROR: --bench N requires N >= 1 (got {iterations})\n")
        return 2

    rc = _run_prewarm(state_path)
    if rc != 0:
        return rc

    samples_ms: list[float] = []
    for idx in range(1, iterations + 1):
        sys.stdout.write(f"=== MEASURE {idx}/{iterations} ===\n")
        sys.stdout.flush()
        boot_ms = _boot_once(measure=True)
        if boot_ms is None:
            sys.stderr.write(f"ERROR: measurement {idx} failed; aborting bench\n")
            return 3
        sys.stdout.write(f"LANGFLOW_NO_CHANGE_RESTART_MS={boot_ms:.2f}\n")
        sys.stdout.flush()
        samples_ms.append(boot_ms)

    out_path = os.environ.get("BENCH_OUTPUT_JSON")
    report_path = Path(out_path) if out_path else state_path / "langflow_run_no_change_restart.json"
    command_repr = " ".join(_langflow_argv())
    _write_hyperfine_report(report_path, command=command_repr, samples_ms=samples_ms)
    sys.stdout.write(f"Wrote bench report: {report_path}\n")
    mean_ms = statistics.fmean(samples_ms)
    stddev_ms = statistics.pstdev(samples_ms) if len(samples_ms) >= 2 else 0.0
    sys.stdout.write(
        f"Summary: mean={mean_ms:.2f}ms stddev={stddev_ms:.2f}ms "
        f"min={min(samples_ms):.2f}ms max={max(samples_ms):.2f}ms runs={len(samples_ms)}\n",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint with three modes."""
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
    group.add_argument(
        "--bench",
        type=int,
        metavar="N",
        default=None,
        help="Pre-warm once, then run N measured boots and write a hyperfine-format report.",
    )
    args = parser.parse_args(argv)
    state_path = _ensure_state_env()
    if args.bench is not None:
        return _run_bench(state_path, iterations=args.bench)
    mode = args.mode or "measure"
    if mode == "prewarm":
        return _run_prewarm(state_path)
    return _run_measure(state_path)


if __name__ == "__main__":
    raise SystemExit(main())
