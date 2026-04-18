"""SVC-01 no-change-restart scenario: measure second-boot wall-clock.

Measures ``langflow run`` when the starter-projects hash matches and the DB has
all rows already present.

Mechanism:
  1. Pre-warm (hyperfine ``--setup``, runs once): supervisor boots langflow, lets
     ``create_or_update_starter_projects`` write the hash file and populate the DB,
     then SIGTERMs. State lives under ``/bench-state`` inside the container, which
     is bind-mounted to a host tmp dir so it survives each ``docker run --rm``.
  2. Measure (hyperfine main command, runs ``runs`` times): supervisor boots
     langflow against the pre-populated state dir. The hash matches, the
     starter-project block exits in milliseconds, and the MCP Event fires
     near-immediately.

Per CONTEXT D-03: this is the authoritative source of the 50ms claim (CI only).
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
    command=[*_SUPERVISOR, "--measure"],
    prewarm_command=[*_SUPERVISOR, "--prewarm"],
    env={
        "LANGFLOW_SUPERUSER": "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": "bench-pass-not-a-real-secret",  # pragma: allowlist secret
    },
    runs=5,
    captures_checkpoints=False,
    captures_pyinstrument=False,
    # importtime is already captured by the regular langflow_run_http_ready scenario;
    # re-capturing it on this measured-boot supervisor would conflate boot output.
    captures_importtime=False,
)
