"""Immutable run context for a single Locust movement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from tests.locust.langflow_runtime.config.env import PerfEnv, load_perf_env
from tests.locust.langflow_runtime.config.models import MovementProfile


@dataclass(frozen=True, slots=True)
class RunContext:
    profile: MovementProfile
    provision_state: dict[str, Any] | None
    host: str
    run_id: str
    report_dir: Path
    env_id: str | None
    overrides: dict[str, Any] = field(default_factory=dict)

    @property
    def profile_path(self) -> str | None:
        value = self.overrides.get("profile_path")
        return str(value) if value is not None else None

    @property
    def state_path(self) -> str | None:
        value = self.overrides.get("state_path")
        return str(value) if value is not None else None


def build_run_context(
    profile: MovementProfile,
    *,
    host: str | None = None,
    run_id: str | None = None,
    report_dir: Path | str | None = None,
    env_id: str | None = None,
    provision_state: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    perf_env: PerfEnv | None = None,
) -> RunContext:
    """Construct a run context from a validated profile and optional overrides."""
    from tests.locust.langflow_runtime.paths import reports_dir

    env = perf_env or load_perf_env()
    resolved_run_id = run_id or uuid4().hex[:12]
    resolved_report_dir = Path(report_dir) if report_dir is not None else reports_dir() / resolved_run_id
    return RunContext(
        profile=profile,
        provision_state=provision_state,
        host=host or env.host,
        run_id=resolved_run_id,
        report_dir=resolved_report_dir,
        env_id=env_id if env_id is not None else env.env_id,
        overrides=dict(overrides or {}),
    )
