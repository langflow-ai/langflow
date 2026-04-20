"""SVC-01 no-change-restart scenario: measure second-boot wall-clock.

Measures ``langflow run`` when the starter-projects hash matches and the DB has
all rows already present. Unlike the hyperfine-wrapped scenarios, this one is
self-measuring: the supervisor does its own pre-warm + measurement loop inside
a single container and writes a hyperfine-compatible JSON report to
``$BENCH_OUTPUT_JSON``. This avoids hyperfine swallowing all output on CI and
keeps iteration progress visible in the workflow log.

Mechanism:
  1. Container launches once (no --rm churn between iterations).
  2. Supervisor pre-warms langflow: boots, lets ``create_or_update_starter_projects``
     write the hash file and populate the DB, SIGTERMs.
  3. Supervisor loops ``runs`` times, each time booting against the pre-populated
     state and timing wall-clock from Popen start to ready marker.
  4. Supervisor writes ``langflow_run_no_change_restart.json`` in hyperfine's
     --export-json shape so the aggregate step reads it unchanged.

Per CONTEXT this is the authoritative source of the 50ms claim (CI only).
The local macOS wall-clock is non-authoritative per Phase 1 Pitfall 3; the
50ms ceiling lives in CI via ``thresholds.json`` + the ``run-benchmark-snapshot``
label pipeline.
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

_SUPERVISOR = [
    "uv",
    "run",
    "python",
    "-m",
    "src.backend.tests.benchmarks.scenarios._langflow_no_change_restart_supervisor",
]

SCENARIO = Scenario(
    name="langflow_run_no_change_restart",
    variant="prebaked",
    command=[*_SUPERVISOR, "--bench", "5"],
    env={
        "LANGFLOW_SUPERUSER": "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": "bench-pass-not-a-real-secret",  # pragma: allowlist secret
    },
    runs=5,
    self_measuring=True,
    captures_checkpoints=False,
    captures_pyinstrument=False,
    # importtime is already captured by the regular langflow_run_http_ready scenario;
    # re-capturing it on this measured-boot supervisor would conflate boot output.
    captures_importtime=False,
)
