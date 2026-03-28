"""Graph checkpoint data model for pause/resume execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class VertexCheckpointData(BaseModel):
    """Serialized state of a single completed vertex."""

    built: bool = False
    results: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    built_object: Any = None
    built_result: Any = None


class GraphCheckpoint(BaseModel):
    """Persistent snapshot of graph execution state at a layer boundary.

    Captures everything needed to resume a paused graph execution:
    the execution progress, completed vertex results, and the reason
    for the pause.
    """

    # Identity
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    flow_id: str
    session_id: str
    run_id: str

    # Graph definition (needed to reconstruct the graph on resume)
    flow_payload: dict[str, Any] = Field(default_factory=dict)

    # Execution state
    completed_layers: int = 0
    run_manager_state: dict[str, Any] = Field(default_factory=dict)
    vertices_to_run: set[str] = Field(default_factory=set)
    vertices_layers: list[list[str]] = Field(default_factory=list)
    inactivated_vertices: set[str] = Field(default_factory=set)
    activated_vertices: list[str] = Field(default_factory=list)
    call_order: list[str] = Field(default_factory=list)

    # Completed vertex results
    vertex_results: dict[str, VertexCheckpointData] = Field(default_factory=dict)

    # Pause context
    paused_vertex_id: str | None = None
    pause_reason: str = ""
    pause_data: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
