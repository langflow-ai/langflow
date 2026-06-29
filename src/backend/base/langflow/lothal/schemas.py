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
    "PROTOTYPE",
    "CODE_GENERATION",
    "DONE",
]
Role = Literal["USER", "ASSISTANT"]
# The Open Design prototype-run lifecycle (Story U.1's ``PrototypeStatus`` ORM
# enum), surfaced on the wire by the prototype endpoints (Story U.0).
PrototypeStatusLiteral = Literal["IDLE", "GENERATING", "READY", "APPROVED"]


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
    """`POST /projects/{id}/chat` body.

    `artifact` is the active artifact key the user is refining in the ARCHITECTURE
    stage (e.g. `diagrams/context.d2` or `adr.md`, Epic E.3) — it routes a refine
    turn to the right artifact in the map. `null`/omitted for non-architecture
    turns and for the first (generation) turn; the architecture engine defaults a
    refine with no target to the sequence diagram (what the single-diagram canvas
    shows today).
    """

    content: str
    artifact: str | None = None


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


class ArtifactsResponse(BaseModel):
    """`GET /projects/{id}/artifacts` — the architecture artifact map + rendered diagrams (Epic E.4).

    The ARCHITECTURE stage emits a flat `{path: content}` artifact map into
    `lothal_project.artifacts` (`adr.md` + `diagrams/*.d2`, Epic E.3) — the future
    git commit tree verbatim. `artifacts` returns that map: `{}` while the project
    is past CLARIFICATION but before the generator has emitted anything (an empty
    map, not an error). Each diagram entry (`diagrams/*.d2`) is also server-rendered
    to SVG via the `d2` compiler and returned in `svgs`, keyed by the same path —
    so the frontend displays the SVG and ships no D2 compiler of its own (the same
    backend-render contract `GET /diagram` honours). The ADR is Markdown and has no
    SVG. An `svgs` value is `null` when its diagram could not be rendered (compiler
    unavailable / render failure), which is logged but never fails the read.
    """

    artifacts: dict[str, str] = Field(default_factory=dict)
    svgs: dict[str, str | None] = Field(default_factory=dict)


class DiagramApproveResponse(BaseModel):
    """`POST /projects/{id}/diagram/approve` — the phase after advancing."""

    phase: Phase


class CodeResponse(BaseModel):
    """`GET /projects/{id}/code` — all generated files (`[]` while in progress)."""

    files: list[CodeFile]


# --- Prototype stage (Epic UI, Story U.0) ------------------------------------
# The prototype stage drives Open Design (OD) as a headless prototyping engine.
# These shapes are the Lothal-side contract the frontend builds against; the
# endpoints ship as 501 stubs in U.0 and fill in over U.4-U.7. Field names stay
# snake_case to match the rest of the Lothal API (the frontend maps them).


class PrototypeArtifactRead(BaseModel):
    """One retained OD prototype artifact, as the UI lists it. Backed by `lothal_prototype_artifact`."""

    path: str
    kind: str
    title: str
    # A ready-to-load preview URL for the artifact (served by OD); `null` until
    # the backend can resolve one.
    preview_url: str | None = None


class PrototypeStateResponse(BaseModel):
    """`GET /projects/{id}/prototype` — prototype run state + OD linkage + embed URL + artifacts.

    Drives the Prototype pane: the UI polls this while `status` is `GENERATING`
    and embeds `embed_url` once `READY`. `od_project_id`/`od_conversation_id` are
    `null` until the stage seeds an OD project (Story U.4); `embed_url` is the
    ready-to-iframe OD URL, resolved by the backend so the client never builds
    OD's routing itself. `artifacts` is empty until the run produces any.
    """

    status: PrototypeStatusLiteral
    od_project_id: str | None = None
    od_conversation_id: str | None = None
    embed_url: str | None = None
    # The primary design artifact's HTML, ready to render inline in a sandboxed
    # iframe — the prototype pane shows the design itself, not OD's web UI. `null`
    # until a design exists.
    preview_html: str | None = None
    artifacts: list[PrototypeArtifactRead] = Field(default_factory=list)


class PrototypeRefineRequest(BaseModel):
    """`POST /projects/{id}/prototype/refine` body — a Lothal-side refine instruction.

    The primary refine path is inside OD itself; this optional secondary path
    lets a refine instruction come from the Langflow chat (a new OD run in the
    same conversation, Story U.6).
    """

    content: str


class PrototypeApproveResponse(BaseModel):
    """`POST /projects/{id}/prototype/approve` — the phase after advancing (→ CODE_GENERATION)."""

    phase: Phase


class DebugLLMResponse(BaseModel):
    """`POST /debug/llm` — the raw model reply."""

    response: str
