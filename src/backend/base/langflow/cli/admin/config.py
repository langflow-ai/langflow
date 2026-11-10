"""Connection configuration for the administration CLI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from platformdirs import user_config_path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

DEFAULT_PROFILE_FILE = user_config_path("langflow") / "admin-profiles.json"


class ConnectionConfigurationError(ValueError):
    """Raised when the CLI cannot resolve a target or credential."""


class AdminProfile(BaseModel):
    """A non-secret target profile.

    The API key is deliberately indirect: only the name of the environment
    variable containing the credential may be stored on disk.
    """

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)


class AdminProfiles(BaseModel):
    """On-disk profile document."""

    model_config = ConfigDict(extra="forbid")

    profiles: dict[str, AdminProfile] = Field(default_factory=dict)


@dataclass(frozen=True)
class AdminConnection:
    """Fully resolved runtime connection settings."""

    url: str
    api_key: str


def _load_profiles(profile_file: Path) -> AdminProfiles:
    if not profile_file.exists():
        return AdminProfiles()
    try:
        raw: Any = json.loads(profile_file.read_text(encoding="utf-8"))
        return AdminProfiles.model_validate(raw)
    except OSError as exc:
        msg = f"Unable to read administration profile file {profile_file}"
        raise ConnectionConfigurationError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Invalid administration profile JSON at line {exc.lineno}, column {exc.colno}"
        raise ConnectionConfigurationError(msg) from exc
    except ValidationError as exc:
        problems = []
        for error in exc.errors(include_input=False, include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            problems.append(f"{location}: {error['msg']}" if location else error["msg"])
        msg = f"Invalid administration profile file {profile_file}: {'; '.join(problems)}"
        raise ConnectionConfigurationError(msg) from exc


def resolve_connection(
    *,
    url: str | None = None,
    api_key: str | None = None,
    profile: str | None = None,
    profile_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AdminConnection:
    """Resolve flags, a selected profile, then process environment variables."""
    environment = os.environ if environ is None else environ
    selected_profile: AdminProfile | None = None
    if profile is not None:
        profiles_path = profile_file or DEFAULT_PROFILE_FILE
        selected_profile = _load_profiles(profiles_path).profiles.get(profile)
        if selected_profile is None:
            msg = f"Administration profile {profile!r} was not found in {profiles_path}"
            raise ConnectionConfigurationError(msg)

    resolved_url = (
        url or (selected_profile.url if selected_profile is not None else None) or environment.get("LANGFLOW_URL")
    )
    resolved_key = api_key
    if resolved_key is None and selected_profile is not None:
        resolved_key = environment.get(selected_profile.api_key_env)
        if not resolved_key:
            msg = (
                f"Administration profile {profile!r} requires credential environment variable "
                f"{selected_profile.api_key_env!r}"
            )
            raise ConnectionConfigurationError(msg)
    resolved_key = resolved_key or environment.get("LANGFLOW_API_KEY")

    if not resolved_url:
        msg = "Langflow URL is required; use --url, select a profile, or set LANGFLOW_URL"
        raise ConnectionConfigurationError(msg)
    if not resolved_key:
        msg = "Langflow API key is required; use --api-key, select a profile, or set LANGFLOW_API_KEY"
        raise ConnectionConfigurationError(msg)
    return AdminConnection(url=resolved_url.rstrip("/"), api_key=resolved_key)
