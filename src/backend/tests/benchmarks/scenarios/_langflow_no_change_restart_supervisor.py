"""Supervisor: SVC-01 no-change-restart benchmark.

Runs ``langflow run`` TWICE in sequence:

  Boot 1 (pre-warm, discarded): ``langflow run`` until ``Application startup complete.``
    appears on stderr, then SIGTERM. This writes ``<config_dir>/starter_projects.hash``
    and populates the DB, so Boot 2 hits the hash-match short-circuit.

  Boot 2 (measured): ``langflow run`` against the SAME ``LANGFLOW_CONFIG_DIR`` and
    ``LANGFLOW_DATABASE_URL`` so the hash gate's short-circuit actually fires. The
    wall-clock for Boot 2 is emitted as ``LANGFLOW_NO_CHANGE_RESTART_MS=<ms>`` on
    stdout. hyperfine measures the total supervisor duration (Boot 1 + Boot 2);
    the per-boot marker is what the reports pick up.

Between boots, ``LANGFLOW_CONFIG_DIR`` + ``LANGFLOW_DATABASE_URL`` are NOT cleared
(that is the whole point: Boot 1's hash file + starter-project DB rows must
persist for Boot 2 to hit the hash-match path). If the ambient environment
does not set them, this supervisor picks a deterministic tmp directory and
exports both vars for the subprocess so the supervisor is self-contained.

Mirrors ``_langflow_supervisor.py`` verbatim for the subprocess+marker
mechanics (READY_MARKER, STARTUP_TIMEOUT_SEC, Popen shape, SIGTERM cleanup);
the only new logic is the two-boot wrapper and the tmp config dir seeding.

Exit codes:
  0 - success (both boots saw the marker; LANGFLOW_NO_CHANGE_RESTART_MS printed).
  2 - timeout (STARTUP_TIMEOUT_SEC elapsed without the marker in one of the boots).
  3 - early exit (process exited before the marker appeared on one of the boots).
"""

from __future__ import annotations

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
# invocation time. The second boot is expected to be dramatically faster; we reuse
# the same generous ceiling for both to keep the supervisor predictable.
STARTUP_TIMEOUT_SEC = float(os.environ.get("LANGFLOW_BENCH_STARTUP_TIMEOUT", "180"))


def _langflow_argv() -> list[str]:
    """Return the ``langflow run`` command used for both boots."""
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


def _boot_once(*, measure: bool) -> float | None:
    """Launch ``langflow run``, wait for ready marker, SIGTERM, return elapsed ms (or None).

    When ``measure`` is False the boot is a pre-warm: the elapsed ms is discarded
    and the return value is ``None`` on success (but still ``None`` on failure --
    the caller distinguishes via the non-zero exit code propagated to process-exit).
    When ``measure`` is True the boot's ready-marker wall-clock in milliseconds is
    returned on success.
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


def _ensure_persistent_state_env() -> None:
    """Export deterministic ``LANGFLOW_CONFIG_DIR`` + ``LANGFLOW_DATABASE_URL`` for both boots.

    If the caller already set them, respect the caller's values (the hyperfine
    wrapper in CI may choose a controlled location). Otherwise pick a scenario-
    specific directory under the system tmp dir so Boot 2 reuses Boot 1's state.
    """
    if not os.environ.get("LANGFLOW_CONFIG_DIR"):
        tmp_root = Path(tempfile.gettempdir()) / "langflow_bench_no_change_restart"
        tmp_root.mkdir(parents=True, exist_ok=True)
        os.environ["LANGFLOW_CONFIG_DIR"] = str(tmp_root)
    if not os.environ.get("LANGFLOW_DATABASE_URL"):
        db_path = Path(os.environ["LANGFLOW_CONFIG_DIR"]) / "bench_no_change_restart.db"
        os.environ["LANGFLOW_DATABASE_URL"] = f"sqlite:///{db_path}"


def main() -> int:
    """Two-boot supervisor entrypoint. Returns process exit code."""
    _ensure_persistent_state_env()

    # Boot 1: pre-warm. Writes hash + populates DB. Elapsed time discarded.
    sys.stdout.write("=== BOOT 1 (pre-warm, discarded) ===\n")
    sys.stdout.flush()
    boot_1 = _boot_once(measure=False)
    if boot_1 is None:
        return 3

    # Boot 2: measured. Hash should match -> short-circuit starter-project sync.
    sys.stdout.write("=== BOOT 2 (measured) ===\n")
    sys.stdout.flush()
    boot_2_ms = _boot_once(measure=True)
    if boot_2_ms is None:
        return 3

    sys.stdout.write(f"LANGFLOW_NO_CHANGE_RESTART_MS={boot_2_ms:.2f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
