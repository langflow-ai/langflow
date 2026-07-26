"""Environment loading for the performance suite."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@dataclass(frozen=True, slots=True)
class PerfCredentials:
    username: str | None
    password: str | None
    api_key: str | None

    def redacted(self) -> dict[str, str | None]:
        return {
            "username": self.username,
            "password": "***" if self.password else None,
            "api_key": "***" if self.api_key else None,
        }


@dataclass(frozen=True, slots=True)
class PerfEnv:
    host: str
    env_id: str | None
    state_path: str | None
    profile_path: str | None
    credentials: PerfCredentials

    def public_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "env_id": self.env_id,
            "state_path": self.state_path,
            "profile_path": self.profile_path,
            "credentials": self.credentials.redacted(),
        }


def load_perf_env() -> PerfEnv:
    """Load performance-suite environment variables without logging secrets."""
    host = _env("PERF_HOST") or _env("LANGFLOW_HOST") or "http://localhost:7860"
    return PerfEnv(
        host=host,
        env_id=_env("PERF_ENV_ID"),
        state_path=_env("PERF_STATE_PATH"),
        profile_path=_env("PERF_PROFILE_PATH"),
        credentials=PerfCredentials(
            username=_env("PERF_SUPERUSER") or _env("LANGFLOW_SUPERUSER"),
            password=_env("PERF_SUPERUSER_PASSWORD") or _env("LANGFLOW_SUPERUSER_PASSWORD"),
            api_key=_env("PERF_API_KEY") or _env("API_KEY"),
        ),
    )
