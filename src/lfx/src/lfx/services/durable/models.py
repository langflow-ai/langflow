"""Typed rows for the lfx durable substrate.

Enum values mirror the langflow job substrate verbatim (``queued`` / ``suspended`` /
``resume`` ...), so a run suspended by one runtime reads the same vocabulary when
resumed through the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SUSPENDED = "suspended"


class JobType(str, Enum):
    WORKFLOW = "workflow"


class SignalType(str, Enum):
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"


@dataclass(frozen=True)
class DurableJob:
    job_id: str
    flow_id: str
    user_id: str
    status: JobStatus
    job_type: JobType
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    job_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DurableEvent:
    job_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class DurableSignal:
    signal_id: int
    job_id: str
    signal_type: SignalType
    data: dict[str, Any]
    created_at: datetime
