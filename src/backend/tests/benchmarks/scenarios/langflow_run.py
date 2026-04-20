"""langflow run scenario. Terminal checkpoint is 127.0.0.1:7860 accepting a TCP connection.

The scenario's command invokes the sibling `_langflow_supervisor.py` as a subprocess-of-a-subprocess
so hyperfine's wall-clock measurement equals time-to-HTTP-ready. `langflow run` starts uvicorn and
does not return; the supervisor polls the bind port and SIGTERMs the child on first connect success.
TCP readiness is used instead of scraping uvicorn's `Application startup complete.` log line because
that line is swallowed by langflow's structlog processor pipeline.
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

SCENARIO = Scenario(
    name="langflow_run_http_ready",
    # Uses the bytecode-compiled image so the langflow_run number reflects production-style
    # boot (langflow images always set UV_COMPILE_BYTECODE=1).
    variant="prebaked",
    # `python` in the container image is the system interpreter without lfx or langflow
    # on sys.path; `uv run python` activates /app/.venv where both packages live.
    command=["uv", "run", "python", "-m", "src.backend.tests.benchmarks.scenarios._langflow_supervisor"],
    env={
        "LANGFLOW_SUPERUSER": "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": "bench-pass-not-a-real-secret",  # pragma: allowlist secret
    },
    runs=5,
    captures_checkpoints=False,
    captures_pyinstrument=True,
    captures_importtime=True,
)
