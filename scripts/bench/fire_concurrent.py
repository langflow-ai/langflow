#!/usr/bin/env python3
"""Spawn N concurrent `lfx run` subprocesses inside the pod and report timings.

Runs INSIDE the benchmark container. The host-side orchestrator invokes this
via `docker exec` once per concurrency level. Centralizing the spawn here
minimizes per-invocation docker-exec overhead and keeps all N subprocesses
starting within microseconds of each other.

Invocation:
    python fire_concurrent.py <N> <input_value>

Emits a single JSON object to stdout:
    {"runs": [{"wall": <seconds>, "exit": <int>,
               "stdout_tail": <str>, "stderr_tail": <str>}, ...]}
"""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
import time

FLOW_PATH = "/app/data/flow.json"
TAIL_BYTES = 400
MIN_ARGC = 2
HAS_INPUT_ARGC = 3


def run_one(input_value: str) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(  # noqa: S603
        ["lfx", "run", FLOW_PATH, input_value, "--format", "json"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    wall = time.perf_counter() - t0
    return {
        "wall": wall,
        "exit": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-TAIL_BYTES:],
        "stderr_tail": (proc.stderr or "")[-TAIL_BYTES:],
    }


def main() -> int:
    if len(sys.argv) < MIN_ARGC:
        sys.exit("usage: fire_concurrent.py <N> [input_value]")
    n = int(sys.argv[1])
    input_value = sys.argv[2] if len(sys.argv) >= HAS_INPUT_ARGC else "hello"
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(lambda _: run_one(input_value), range(n)))
    print(json.dumps({"runs": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
