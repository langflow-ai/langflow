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
from pydantic import BaseModel, Field, field_validator

Phase = Literal[
    "CLARIFICATION",
    "ARCHITECTURE",
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

        The ORM stores `diagram_json` as a JSON string (the legacy xyflow graph —
        nodes-with-positions + edges); every reader receives the parsed object
        from here. Nothing writes this column any more (Epic D made D2 the diagram
        artifact and D.13 backfills the legacy data into `diagram_d2`); it is kept
        for pre-D2 projects until a later column-drop migration. A malformed or
        non-object value is logged and exposed as `null` — one bad row must never
        fail a whole project read or list response.
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


class DebugLLMRequest(BaseModel):
    """`POST /debug/llm` body."""

    message: str


# --- response bodies ---------------------------------------------------------


class PRDResponse(BaseModel):
    """`GET /projects/{id}/prd` — `null` until the project leaves CLARIFICATION."""

    content: str | None


class DiagramResponse(BaseModel):
    """`GET /projects/{id}/diagram` — D2 source + server-rendered SVG (Epic D.4/D.6).

    The diagram artifact is D2 source text now, not an xyflow graph (that was
    Story 2.3). `d2` is the stored `lothal_project.diagram_d2`, returned verbatim:
    `null` while the project is past CLARIFICATION but before the generator has
    emitted anything (an empty payload, not an error). `svg` is that source
    rendered to SVG by the backend `d2` compiler (D.6) — the frontend displays it
    and ships no D2 compiler of its own. `svg` is `null` when there is no `d2`, or
    if rendering was not possible (compiler unavailable / render failure), which
    is logged but never fails the read.
    """

    d2: str | None = None
    svg: str | None = None


class DiagramApproveResponse(BaseModel):
    """`POST /projects/{id}/diagram/approve` — the phase after advancing."""

    phase: Phase


class CodeResponse(BaseModel):
    """`GET /projects/{id}/code` — all generated files (`[]` while in progress)."""

    files: list[CodeFile]


class DebugLLMResponse(BaseModel):
    """`POST /debug/llm` — the raw model reply."""

    response: str
