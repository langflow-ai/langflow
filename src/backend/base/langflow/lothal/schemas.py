"""Pydantic request/response schemas for the Lothal API contract.

These mirror `api-endpoints.md` exactly. They document the full `/api/v1/lothal/`
surface in OpenAPI while the backends are still 501 stubs (Story A.1). As each
endpoint goes live, its handler returns these same models unchanged — the
contract (and therefore the UI built against it) never moves.
"""

import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from lfx.log.logger import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator

Phase = Literal[
    "CLARIFICATION",
    "DIAGRAM_GENERATION",
    "DIAGRAM_REFINEMENT",
    "CODE_GENERATION",
    "DONE",
]
Role = Literal["USER", "ASSISTANT"]


class NotImplementedResponse(BaseModel):
    """Structured `501` body. Every not-yet-built endpoint returns this shape.

    The frontend keys a single `NotReady` state off it, so every unbuilt surface
    looks consistent without per-screen error handling.
    """

    detail: str
    status: Literal["not_implemented"] = "not_implemented"


# --- xyflow render layer -----------------------------------------------------


class Position(BaseModel):
    """Canvas coordinates for a node."""

    x: float
    y: float


class NodeData(BaseModel):
    """Node payload. `label` is the only guaranteed field.

    The Mermaid↔xyflow converter may add optional render hints (`kind`, `note`)
    that are not part of the LLM contract, so extra keys are permitted.
    """

    model_config = ConfigDict(extra="allow")

    label: str


class Node(BaseModel):
    """An xyflow node (`actorNode` or `systemNode`)."""

    id: str
    type: Literal["actorNode", "systemNode"]
    data: NodeData
    position: Position


class EdgeData(BaseModel):
    """Edge payload. `order` is the line index; optional `kind` is a render hint."""

    model_config = ConfigDict(extra="allow")

    order: int


class Edge(BaseModel):
    """An xyflow edge between two participants."""

    id: str
    source: str
    target: str
    label: str
    data: EdgeData


# --- core resources ----------------------------------------------------------


class ProjectRead(BaseModel):
    """A Lothal project and its current phase. Backed by `lothal_project`."""

    id: UUID
    user_id: UUID
    name: str
    phase: Phase
    prd_content: str | None = None
    diagram_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("diagram_json", mode="before")
    @classmethod
    def _parse_diagram_json(cls, value: Any) -> Any:
        """Parse the stored JSON string once, at the schema boundary.

        The ORM stores `diagram_json` as a JSON string (the full xyflow graph —
        nodes-with-positions + edges); every reader receives the parsed object
        from here, and the diagram-save story must serialize back through this
        same boundary. A malformed or non-object value is logged and exposed as
        `null` — one bad row must never fail a whole project read or list
        response.
        """
        if value is None or isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            logger.warning("Ignoring malformed diagram_json; exposing null.")
            return None
        if not isinstance(parsed, dict):
            logger.warning("Ignoring non-object diagram_json; exposing null.")
            return None
        return parsed


class MessageRead(BaseModel):
    """A chat message. `suggestions` is `[]` except for clarification replies."""

    id: UUID
    project_id: UUID
    role: Role
    content: str
    suggestions: list[str] = Field(default_factory=list)
    phase: str
    created_at: datetime


class CodeFile(BaseModel):
    """A single generated code file. Backed by `lothal_code_file`."""

    path: str
    content: str


# --- request bodies ----------------------------------------------------------


class ProjectCreate(BaseModel):
    """`POST /projects/` body."""

    name: str


class ChatRequest(BaseModel):
    """`POST /projects/{id}/chat` body."""

    content: str


class DiagramSaveRequest(BaseModel):
    """`POST /projects/{id}/diagram/save` body — the current canvas state."""

    nodes: list[Node]
    edges: list[Edge]


class DebugLLMRequest(BaseModel):
    """`POST /debug/llm` body."""

    message: str


# --- response bodies ---------------------------------------------------------


class PRDResponse(BaseModel):
    """`GET /projects/{id}/prd` — `null` until the project leaves CLARIFICATION."""

    content: str | None


class DiagramSaveResponse(BaseModel):
    """`POST /projects/{id}/diagram/save` — serialized Mermaid plus any validation warning."""

    mermaid: str
    validation_message: str | None


class DiagramApproveResponse(BaseModel):
    """`POST /projects/{id}/diagram/approve` — the phase after advancing."""

    phase: Phase


class CodeResponse(BaseModel):
    """`GET /projects/{id}/code` — all generated files (`[]` while in progress)."""

    files: list[CodeFile]


class DebugLLMResponse(BaseModel):
    """`POST /debug/llm` — the raw model reply."""

    response: str
