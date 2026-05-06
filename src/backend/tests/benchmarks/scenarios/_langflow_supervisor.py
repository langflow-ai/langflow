"""Supervisor: launches `langflow run`, exits when 127.0.0.1:7860 accepts a TCP connection.

hyperfine measures the wall-clock duration of this supervisor, which equals
time-to-HTTP-ready. That's the langflow_run_http_ready scenario.

Readiness detection: TCP connect success against the server's bind address. The
uvicorn `Application startup complete.` stdout marker is swallowed by langflow's
structlog processor pipeline, so scraping it races under load. TCP connect is a
ground-truth readiness signal that does not depend on logging at all. The same
approach is used by _langflow_no_change_restart_supervisor.py.

Exit codes:
  0 - success (port reachable; LANGFLOW_READY_MS printed to stdout).
  2 - timeout (STARTUP_TIMEOUT_SEC elapsed without the port accepting connections).
  3 - early exit (process exited before the port was reachable).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time

READY_HOST = "127.0.0.1"
READY_PORT = 7860
# Short enough to keep measurement noise bounded; long enough to avoid
# trivial CPU burn during the ~30-40s cold boot on Linux CI.
READY_POLL_INTERVAL_SEC = 0.05
# 60s is sufficient on Linux CI. macOS/podman runs with an emulated VM need more
# headroom; `LANGFLOW_BENCH_STARTUP_TIMEOUT` overrides at invocation time.
STARTUP_TIMEOUT_SEC = float(os.environ.get("LANGFLOW_BENCH_STARTUP_TIMEOUT", "180"))


def _tcp_ready(host: str, port: int, *, connect_timeout: float = 0.5) -> bool:
    """Return True if a TCP connection to ``(host, port)`` succeeds within the deadline."""
    try:
        with socket.create_connection((host, port), timeout=connect_timeout):
            return True
    except OSError:
        return False


def _drain_output(stream, stop_event: threading.Event) -> None:
    """Forward the child's merged stdout to our stdout so CI logs show boot progress.

    Runs in a background thread so the main thread can poll TCP readiness without
    blocking on ``readline``. When ``stop_event`` fires we stop reading even if the
    child is still producing output.
    """
    try:
        for line in stream:
            if stop_event.is_set():
                break
            sys.stdout.write(line)
            sys.stdout.flush()
    except (ValueError, OSError):
        return


def main() -> int:
    """Launch `langflow run`, wait for TCP readiness, terminate cleanly."""
    # Pre-flight: if something is already bound to the scenario port, any TCP
    # probe we run against our own child will race against that listener and
    # silently record a near-zero LANGFLOW_READY_MS. Refuse to measure rather
    # than produce garbage numbers.
    if _tcp_ready(READY_HOST, READY_PORT, connect_timeout=0.1):
        sys.stderr.write(
            f"ERROR: {READY_HOST}:{READY_PORT} already accepts connections before "
            f"the supervisor started its child; another process (dev server, leftover "
            f"benchmark boot) is squatting the port.\n",
        )
        return 3

    start = time.perf_counter()
    proc = subprocess.Popen(  # noqa: S603
        [  # noqa: S607
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
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        sys.stderr.write("ERROR: Popen did not provide a stdout stream\n")
        return 3

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
                # Defense in depth: if the connect succeeded but our child is
                # already gone, we hit a listener that isn't ours. Don't record
                # a bogus LANGFLOW_READY_MS.
                if proc.poll() is not None:
                    sys.stderr.write(
                        f"ERROR: {READY_HOST}:{READY_PORT} connected but child exited "
                        f"(rc={proc.returncode}); another listener is squatting the port.\n",
                    )
                    return 3
                ready_at = time.perf_counter()
                break
            if proc.poll() is not None:
                sys.stderr.write(
                    f"ERROR: process exited (rc={proc.returncode}) before {READY_HOST}:{READY_PORT} was ready\n",
                )
                return 3
            if time.perf_counter() - start > STARTUP_TIMEOUT_SEC:
                sys.stderr.write(
                    f"TIMEOUT: {STARTUP_TIMEOUT_SEC}s elapsed without "
                    f"{READY_HOST}:{READY_PORT} accepting connections\n",
                )
                return 2
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

    elapsed_ms = (ready_at - start) * 1000.0
    sys.stdout.write(f"LANGFLOW_READY_MS={elapsed_ms:.2f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
