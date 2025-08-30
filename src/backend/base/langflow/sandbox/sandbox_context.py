"""Execution context and trust level definitions for sandbox execution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ComponentTrustLevel(str, Enum):
    """Trust levels for component execution with corresponding security profiles."""

    UNTRUSTED = "untrusted"     # User-modified code, runs in sandbox with restrictions
    VERIFIED = "verified"       # Original, unmodified components, runs without sandbox


@dataclass
class SandboxExecutionContext:
    """Context information for sandbox execution."""

    execution_id: str
    execution_type: str  # e.g., "custom_component", "python_repl", "code_tool"
    component_path: str
    component_id: str | None = None
    flow_id: str | None = None
    user_id: str | None = None
    timeout: int = 30
    max_memory_mb: int = 128
    max_cpu_time: int = 30
    allow_network: bool = False
    allow_file_access: bool = False
    secrets_required: bool = False
    created_at: datetime = None

    def __post_init__(self):
        if self.execution_id is None:
            self.execution_id = str(uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxExecutionContext:
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> SandboxExecutionContext:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SandboxExecutionResult:
    """Result of sandbox execution."""

    execution_id: str
    success: bool
    result: Any = None
    error: str | None = None
    error_category: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    execution_time: float | None = None
    memory_used: int | None = None
    cpu_time_used: float | None = None
    exit_code: int | None = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxExecutionResult:
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class SandboxConfig(BaseModel):
    """Configuration for sandbox execution."""

    nsjail_path: str = "/usr/bin/nsjail"
    sandbox_root: str = "/var/lib/langflow-sandbox"
    python_path: str = "/usr/bin/python3"
    executor_script: str = "/sandbox/executor.py"

    # Resource limits
    default_timeout: int = 30
    default_memory_limit: int = 128  # MB
    default_cpu_time: int = 30  # seconds
    max_file_size: int = 10  # MB
    max_open_files: int = 32

    # Code size limits (can be overridden per profile)
    untrusted_max_code_kb: int | None = None  # None means use profile default

    # Security settings
    sandbox_user: str = "nobody"
    sandbox_group: str = "nogroup"
    enable_network_isolation: bool = True
    enable_user_isolation: bool = True
    lock_components: bool = Field(default_factory=lambda: __import__("os").getenv("LANGFLOW_SANDBOX_LOCK_COMPONENTS", "false").lower() in ("true", "1", "yes"), description="When true, prevents untrusted components from executing")

    # Paths
    python_lib_paths: list[str] = [
        "/usr/lib/python3.11",
        "/usr/local/lib/python3.11"
    ]

    ssl_cert_paths: list[str] = [
        "/etc/ssl/certs",
        "/usr/share/ca-certificates"
    ]

    # Environment
    base_env_vars: dict[str, str] = {
        "PYTHONPATH": "/opt/langflow/src/backend/base",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1"
    }

    class Config:
        arbitrary_types_allowed = True


@dataclass
class SandboxMetrics:
    """Metrics collected during sandbox execution."""

    execution_id: str
    start_time: datetime
    end_time: datetime | None = None
    cpu_time_user: float | None = None
    cpu_time_system: float | None = None
    memory_peak: int | None = None  # bytes
    memory_current: int | None = None  # bytes
    disk_read_bytes: int | None = None
    disk_write_bytes: int | None = None
    network_sent_bytes: int | None = None
    network_recv_bytes: int | None = None
    exit_status: int | None = None

    def duration(self) -> float | None:
        """Calculate execution duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        data["duration"] = self.duration()
        return data
