"""langflow run scenario. Terminal checkpoint is uvicorn's `Application startup complete.` line.

The scenario's command invokes the sibling `_langflow_supervisor.py` as a subprocess-of-a-subprocess
so hyperfine's wall-clock measurement equals time-to-HTTP-ready.

Per Claude's Discretion in 01-CONTEXT.md and Pitfall 7 in 01-RESEARCH.md: `langflow run` starts
uvicorn and does not return. The supervisor reads stderr line-by-line, records `time.perf_counter()`
when "Application startup complete." appears, then SIGTERMs the child.
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

SCENARIO = Scenario(
    name="langflow_run_http_ready",
    # Uses the bytecode-compiled image so the langflow_run number reflects production-style
    # boot (langflow images always set UV_COMPILE_BYTECODE=1).
    variant="prebaked",
    command=["python", "-m", "src.backend.tests.benchmarks.scenarios._langflow_supervisor"],
    env={
        "LANGFLOW_SUPERUSER": "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": "bench-pass-not-a-real-secret",  # pragma: allowlist secret
    },
    runs=5,
    captures_checkpoints=False,
    captures_pyinstrument=True,
    captures_importtime=True,
)
