"""Isolation configuration for the FileSystem tool.

A frozen dataclass + a single factory that reads environment variables and
produces an immutable ``IsolationConfig``. Keeping this in its own module lets
the component code (``filesystem.py``) treat user-isolation policy as data,
not as scattered ``os.environ.get`` calls.

Policy:
    LANGFLOW_FS_TOOL_USER_ISOLATION  = off | auto | on   (default: auto)
    LANGFLOW_FS_TOOL_BASE_DIR        = absolute path     (default: <config>/fs_sandbox)
    LANGFLOW_FS_TOOL_PEPPER_PATH     = absolute path     (default: <config>/.fs_pepper)
    LANGFLOW_FS_TOOL_AUDIT_LOG       = absolute path | "" (default: disabled)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

ISOLATION_ENV = "LANGFLOW_FS_TOOL_USER_ISOLATION"
BASE_DIR_ENV = "LANGFLOW_FS_TOOL_BASE_DIR"
PEPPER_PATH_ENV = "LANGFLOW_FS_TOOL_PEPPER_PATH"
AUDIT_LOG_ENV = "LANGFLOW_FS_TOOL_AUDIT_LOG"

DEFAULT_BASE_DIR_NAME = "fs_sandbox"
DEFAULT_PEPPER_FILENAME = ".fs_pepper"


class IsolationMode(str, Enum):
    """Per-user isolation policy.

    OFF
        Legacy behavior. ``root_path`` is taken at face value, no namespace
        suffix is appended, no audit policy is enforced. Single-tenant only.
    AUTO
        Apply isolation when a ``user_id`` is available; fall back to legacy
        when the call is anonymous (e.g., scheduled tasks).
    ON
        Hard requirement. Anonymous calls are refused with a structured error.
    """

    OFF = "off"
    AUTO = "auto"
    ON = "on"


@dataclass(frozen=True)
class IsolationConfig:
    """Resolved policy for a FileSystem tool instance — immutable by contract."""

    mode: IsolationMode
    base_dir: Path
    pepper_path: Path
    audit_log_path: Path | None


def resolve_isolation_mode(value: str | None) -> IsolationMode:
    """Parse an env-var value into an IsolationMode.

    Empty / None defaults to AUTO so OSS deployments that never touch the env
    var get a safe, identity-aware default the moment a user_id is wired in.
    """
    if value is None:
        return IsolationMode.AUTO
    cleaned = value.strip().lower()
    if not cleaned:
        return IsolationMode.AUTO
    try:
        return IsolationMode(cleaned)
    except ValueError as exc:
        msg = f"{ISOLATION_ENV} must be one of {', '.join(m.value for m in IsolationMode)}; got {value!r}"
        raise ValueError(msg) from exc


def load_isolation_config(
    *,
    env: Mapping[str, str],
    default_config_dir: Path,
) -> IsolationConfig:
    """Build an immutable IsolationConfig from environment variables.

    Why ``env`` is injected: lets tests pass a tiny dict instead of patching
    ``os.environ`` (which leaks across xdist workers and is order-dependent).
    """
    mode = resolve_isolation_mode(env.get(ISOLATION_ENV))

    base_dir_raw = env.get(BASE_DIR_ENV) or str(default_config_dir / DEFAULT_BASE_DIR_NAME)
    pepper_path_raw = env.get(PEPPER_PATH_ENV) or str(default_config_dir / DEFAULT_PEPPER_FILENAME)
    audit_log_raw = env.get(AUDIT_LOG_ENV)

    audit_log_path: Path | None = Path(audit_log_raw).resolve() if audit_log_raw and audit_log_raw.strip() else None

    return IsolationConfig(
        mode=mode,
        base_dir=Path(base_dir_raw).resolve(),
        pepper_path=Path(pepper_path_raw).resolve(),
        audit_log_path=audit_log_path,
    )
