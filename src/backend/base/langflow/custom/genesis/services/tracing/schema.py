"""Schema definitions for tracing services."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Log(BaseModel):
    """Log entry in a trace."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = "INFO"
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceData(BaseModel):
    """Complete trace data structure."""

    trace_id: UUID
    trace_name: str
    trace_type: str
    project_name: str
    start_time: datetime
    end_time: datetime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    logs: list[Log] = Field(default_factory=list)


class ComponentTrace(BaseModel):
    """Individual component trace within a flow."""

    component_id: str
    component_name: str
    component_type: str
    start_time: datetime
    end_time: datetime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    logs: list[Log] = Field(default_factory=list)

    # Healthcare-specific fields
    patient_id: str | None = None
    encounter_id: str | None = None
    phi_present: bool = False

    # Cost tracking
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost: float = 0.0
