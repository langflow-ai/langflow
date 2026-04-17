"""SVC-01 no-change-restart scenario: measure second-boot wall-clock.

Measures ``langflow run`` when the starter-projects hash matches and the DB has
all rows already present.

Mechanism:
  1. Pre-warm: supervisor boots langflow once (writes hash, populates DB), SIGTERMs.
  2. Measure: supervisor boots langflow a second time with the same config_dir + DB;
     hash matches, starter-project block exits in milliseconds, MCP Event fires
     near-immediately.

Per CONTEXT D-03: this is the authoritative source of the 50ms claim (CI only).
The local macOS wall-clock is non-authoritative per Phase 1 Pitfall 3; the
50ms ceiling lives in CI via ``thresholds.json`` + the ``run-benchmark-snapshot``
label pipeline.
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

SCENARIO = Scenario(
    name="langflow_run_no_change_restart",
    variant="prebaked",
    command=[
        "uv",
        "run",
        "python",
        "-m",
        "src.backend.tests.benchmarks.scenarios._langflow_no_change_restart_supervisor",
    ],
    env={
        "LANGFLOW_SUPERUSER": "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": "bench-pass-not-a-real-secret",  # pragma: allowlist secret
    },
    runs=5,
    captures_checkpoints=False,
    captures_pyinstrument=True,
    # importtime is already captured by the regular langflow_run_http_ready scenario;
    # re-capturing it on this two-boot supervisor would conflate boot 1 + boot 2 output.
    captures_importtime=False,
)
