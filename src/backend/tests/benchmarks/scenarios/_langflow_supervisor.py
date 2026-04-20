"""Supervisor: launches `langflow run`, exits when "Application startup complete." appears on stderr.

Per Pitfall 7 in 01-RESEARCH.md:
  - langflow run starts uvicorn and does not return.
  - Terminal checkpoint = uvicorn's `Application startup complete.` log line.
  - Supervisor reads stdout+stderr line-by-line, records time.perf_counter(), then SIGTERMs.

hyperfine measures the wall-clock duration of THIS supervisor, which equals
time-to-HTTP-ready. That's the MEAS-01 langflow_run scenario.

Exit codes:
  0 - success (ready marker observed; LANGFLOW_READY_MS printed to stdout).
  2 - timeout (STARTUP_TIMEOUT_SEC elapsed without observing the marker).
  3 - early exit (process exited before the marker appeared).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

READY_MARKER = "Application startup complete."
# 60s is sufficient on Linux CI (typical cold boot is 30-40s). macOS/podman runs with an
# emulated VM need more headroom; `LANGFLOW_BENCH_STARTUP_TIMEOUT` overrides at invocation time.
STARTUP_TIMEOUT_SEC = float(os.environ.get("LANGFLOW_BENCH_STARTUP_TIMEOUT", "180"))


def main() -> int:
    """Launch `langflow run`, wait for readiness marker, terminate cleanly. Returns process exit code."""
    start = time.perf_counter()
    proc = subprocess.Popen(
        [  # noqa: S607
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
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        sys.stderr.write("ERROR: Popen did not provide a stdout stream\n")
        return 3

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
                return 2
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
        return 3

    elapsed_ms = (ready_at - start) * 1000.0
    sys.stdout.write(f"LANGFLOW_READY_MS={elapsed_ms:.2f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
