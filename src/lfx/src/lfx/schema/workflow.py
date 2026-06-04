"""Workflow execution schemas for V2 API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, computed_field, model_validator

from lfx.schema.validators import null_check_validator, uuid_validator

# Bounds on body-transported global variables. Keys are intentionally liberal
# (the Langflow UI accepts lowercase, digits, underscore, hyphen, and spaces);
# we only constrain length so a single field can't push the request past a
# reasonable size. Values are capped at 64 KB, which comfortably exceeds the
# longest tokens/secrets stored as global variables in practice.
GLOBAL_KEY_MAX_LEN = 256
GLOBAL_VALUE_MAX_LEN = 64 * 1024

GlobalVarKey = Annotated[str, StringConstraints(min_length=1, max_length=GLOBAL_KEY_MAX_LEN)]
GlobalVarValue = Annotated[str, StringConstraints(max_length=GLOBAL_VALUE_MAX_LEN)]


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


JobId = Annotated[
    str | UUID,
    BeforeValidator(lambda v: null_check_validator(v, message="job_id is required")),
    BeforeValidator(lambda v: uuid_validator(v, message="Invalid job_id, must be a UUID")),
]


class ErrorDetail(BaseModel):
    """Error detail schema."""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


class ComponentOutput(BaseModel):
    """Component output schema."""

    type: str = Field(..., description="Type of the component output (e.g., 'message', 'data', 'tool', 'text')")
    status: JobStatus
    display_name: str | None = Field(
        default=None,
        description="Human-readable component name. The stable component id remains the ``outputs`` dict key.",
    )
    content: Any | None = None
    metadata: dict[str, Any] | None = None


class OutputEvent(ComponentOutput):
    """A single component's output, as emitted on the ``langflow`` stream protocol.

    The streaming counterpart of a sync ``outputs[id]`` entry: the same
    ``ComponentOutput`` payload plus ``component_id`` (which sync carries as the
    dict key). Subclassing keeps the shared fields from drifting, so one parser
    reads ``type``/``status``/``display_name``/``content``/``metadata`` off both the
    sync ``outputs`` map and the stream ``output`` events.
    """

    component_id: str = Field(..., description="Stable component id that produced this output.")


class OutputReason(str, Enum):
    """Why ``WorkflowOutput.text`` resolved the way it did.

    Mirrors the LLM-domain ``finish_reason`` / ``stop_reason`` convention: a
    machine-readable enum explaining the disposition of the answer, distinct from
    the lifecycle ``status``.
    """

    SINGLE = "single"  # exactly one text answer; ``text`` holds it
    MULTIPLE = "multiple"  # two or more text answers; read ``outputs`` and pick
    NONE = "none"  # no text channel at all (e.g. a data-only flow)
    NON_STRING = "non_string"  # a text channel exists but its content isn't a string
    FAILED = "failed"  # the run failed before producing an answer


class WorkflowOutput(BaseModel):
    """The run's primary text answer plus the reason it resolved that way."""

    reason: OutputReason = Field(
        description=(
            "Why ``text`` is or isn't populated. ``single`` means ``text`` holds the answer; "
            "``multiple`` / ``none`` / ``non_string`` / ``failed`` mean ``text`` is null and name "
            "why, so callers never have to guess."
        )
    )
    text: str | None = Field(
        default=None,
        description="The run's text answer. Set only when ``reason`` is ``single``. Empty string is a valid answer.",
    )
    source: str | None = Field(
        default=None,
        description="Component id that produced ``text``. Set only when ``reason`` is ``single``.",
    )


class WorkflowExecutionRequest(BaseModel):
    """Request schema for workflow execution."""

    background: bool = False
    stream: bool = False
    flow_id: str
    inputs: dict[str, Any] | None = Field(
        None, description="Component-specific inputs in flat format: 'component_id.param_name': value"
    )
    globals: dict[GlobalVarKey, GlobalVarValue] = Field(
        default_factory=dict,
        description=(
            "Request-level global variables made available to workflow components. "
            "Keys may use any printable string up to "
            f"{GLOBAL_KEY_MAX_LEN} chars; values are capped at "
            f"{GLOBAL_VALUE_MAX_LEN} chars. Body globals always win over the "
            "legacy ``X-LANGFLOW-GLOBAL-VAR-*`` headers."
        ),
    )

    @model_validator(mode="after")
    def validate_execution_mode(self) -> WorkflowExecutionRequest:
        if self.background and self.stream:
            err_msg = "Both 'background' and 'stream' cannot be True"
            raise ValueError(err_msg)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "background": False,
                    "stream": False,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {
                        "ChatInput-abc.input_value": "Hello, how can you help me today?",
                        "ChatInput-abc.session_id": "session-123",
                        "LLM-xyz.temperature": 0.7,
                        "LLM-xyz.max_tokens": 100,
                        "OpenSearch-def.opensearch_url": "https://opensearch:9200",
                    },
                    "globals": {
                        "FILENAME": "relatorio-final.pdf",
                        "OWNER_NAME": "Jose",
                    },
                },
                {
                    "background": True,
                    "stream": False,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {
                        "ChatInput-abc.input_value": "Process this in the background",
                    },
                },
                {
                    "background": False,
                    "stream": True,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {
                        "ChatInput-abc.input_value": "Stream this conversation",
                    },
                },
            ]
        },
        extra="forbid",
    )


class WorkflowMode(str, Enum):
    """Execution mode for a v2 workflow run."""

    SYNC = "sync"
    STREAM = "stream"
    BACKGROUND = "background"


class WorkflowRunRequest(BaseModel):
    """Request schema for ``POST /api/v2/workflows`` (v2 native body).

    First-class fields for everything callers actually configure when running a
    flow. Streaming protocol is selected by ``stream_protocol``; the endpoint
    validates it against the live adapter registry and returns 422 with the
    available list when unknown.
    """

    flow_id: str = Field(..., description="UUID of the flow to run.")
    input_value: str = Field("", description="Chat-style input value.")
    tweaks: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-component parameter overrides keyed by component id.",
    )
    session_id: str | None = Field(
        None,
        description="When set, message memory and chat history scope to this session.",
    )
    mode: WorkflowMode = Field(
        WorkflowMode.SYNC,
        description=(
            "Execution mode. ``sync`` runs inline and returns the aggregated "
            "response; ``stream`` returns SSE; ``background`` queues a job."
        ),
    )
    stream_protocol: str = Field(
        "langflow",
        description=(
            "Wire protocol for streaming events. Defaults to ``langflow`` "
            "(raw EventManager payloads). ``agui`` emits AG-UI events. Unknown "
            "values return 422 with the available list. Ignored when mode=sync."
        ),
    )
    data: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional live-canvas override of the flow's nodes/edges; takes priority over the saved flow data."
        ),
    )
    files: list[str] | None = Field(
        None,
        description="Optional list of pre-uploaded file paths to attach to the run.",
    )
    start_component_id: str | None = Field(None, description="Partial-run start component id.")
    stop_component_id: str | None = Field(None, description="Partial-run stop component id.")
    output_ids: list[str] | None = Field(
        None,
        description=(
            "Component ids of the outputs you want as the answer (sync mode). When set, "
            "``output.text`` resolves among only these, so naming one text output makes "
            "``output.reason`` deterministic on multi-output flows. The full ``outputs`` "
            "map is still returned. Ids must be outputs of this flow or the request is "
            "rejected before the flow runs. Ignored for stream/background modes."
        ),
    )
    globals: dict[GlobalVarKey, GlobalVarValue] = Field(
        default_factory=dict,
        description=(
            "Request-level global variables made available to workflow components. "
            "Keys may use any printable string up to "
            f"{GLOBAL_KEY_MAX_LEN} chars; values are capped at "
            f"{GLOBAL_VALUE_MAX_LEN} chars. Body globals always win over the "
            "legacy ``X-LANGFLOW-GLOBAL-VAR-*`` headers."
        ),
    )
    idempotency_key: str | None = Field(
        None,
        description=(
            "Optional client-supplied key that dedupes background submits. Two "
            "background runs with the same key return the same job_id instead of "
            "queuing duplicate work. Ignored for sync/stream modes."
        ),
        max_length=255,
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Hello, how can you help me today?",
                },
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Stream this conversation",
                    "mode": "stream",
                },
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Drive the canvas",
                    "mode": "stream",
                    "stream_protocol": "agui",
                    "session_id": "session-123",
                },
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Process in the background",
                    "mode": "background",
                },
            ],
        },
    )

    @model_validator(mode="after")
    def validate_flow_id(self) -> WorkflowRunRequest:
        """Reject non-UUID ``flow_id`` early so the endpoint can trust it."""
        uuid_validator(self.flow_id, message="Invalid flow_id, must be a UUID")
        return self


class PublicWorkflowRunRequest(BaseModel):
    """Request schema for ``POST /api/v2/workflows/public``.

    Narrower than ``WorkflowRunRequest`` so the public-flow surface stays
    locked down. Notably absent vs the regular body:

    - ``data`` — visitors must never override the stored flow definition.
    - ``tweaks`` — visitors must never override component parameters.

    The endpoint enforces the additional CVE mitigations that the regular
    endpoint does not need:

    - ``access_type == PUBLIC`` gate (others 403).
    - ``virtual_flow_id = uuid5(identifier, flow_id)`` so messages stay
      isolated per visitor.
    - Session string namespaced under the virtual flow id
      (CVE-2026-33017).
    - File-path validation (GHSA-rcjh-r59h-gq37).
    - Owner impersonation: the run executes under the flow owner's
      permissions, never the visitor's.
    """

    flow_id: str = Field(..., description="UUID of the public flow to run.")
    input_value: str = Field("", description="Chat-style input value.")
    session_id: str | None = Field(
        None,
        description=("Optional caller session. Always namespaced under the visitor's virtual flow id by the endpoint."),
    )
    mode: Literal[WorkflowMode.STREAM] = Field(
        WorkflowMode.STREAM,
        description=(
            "Always ``stream``. Sync/background modes would widen the public "
            "attack surface (job polling, owner impersonation persists across "
            "queue boundaries) so the schema rejects them at the wire."
        ),
    )
    stream_protocol: str = Field(
        "langflow",
        description=(
            "Wire protocol for streaming events. Defaults to ``langflow`` "
            "(raw EventManager payloads). ``agui`` emits AG-UI events. Unknown "
            "values return 422 with the available list."
        ),
    )
    files: list[str] | None = Field(
        None,
        description=(
            "Optional list of pre-uploaded file paths. Each path must be "
            "scoped to this flow's own storage namespace; the endpoint "
            "rejects path traversal or cross-flow references."
        ),
    )
    start_component_id: str | None = Field(None, description="Partial-run start component id.")
    stop_component_id: str | None = Field(None, description="Partial-run stop component id.")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Hello from the shareable playground",
                },
                {
                    "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
                    "input_value": "Stream the response",
                    "stream_protocol": "agui",
                    "session_id": "thread-A",
                },
            ],
        },
    )

    @model_validator(mode="after")
    def validate_flow_id(self) -> PublicWorkflowRunRequest:
        """Reject non-UUID ``flow_id`` early so the endpoint can trust it."""
        uuid_validator(self.flow_id, message="Invalid flow_id, must be a UUID")
        return self


class WorkflowExecutionResponse(BaseModel):
    """Synchronous workflow execution response."""

    flow_id: str
    session_id: str | None = Field(
        default=None,
        description=(
            "The session the run executed under. Echoes the request ``session_id`` "
            "when provided, otherwise the server-generated one. Pass it back on the "
            "next call to continue the same chat history / memory thread."
        ),
    )
    job_id: JobId | None = None
    object: Literal["response"] = Field(default="response")
    created_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: JobStatus
    output: WorkflowOutput = Field(
        default_factory=lambda: WorkflowOutput(reason=OutputReason.NONE),
        description=(
            "The run's text answer plus why it resolved that way. Read ``output.text`` for the "
            "answer; when it's null, ``output.reason`` says why (``multiple`` / ``none`` / "
            "``non_string`` / ``failed``) so you know whether to read ``outputs``."
        ),
    )
    errors: list[ErrorDetail] = []
    inputs: dict[str, Any] = {}
    globals: dict[GlobalVarKey, GlobalVarValue] = Field(default_factory=dict)
    outputs: dict[str, ComponentOutput] = {}

    @computed_field
    @property
    def has_errors(self) -> bool:
        """True when the run reported any error. Derived from ``errors`` so it can't drift."""
        return len(self.errors) > 0


class WorkflowJobResponse(BaseModel):
    """Background job response."""

    job_id: JobId
    flow_id: str
    object: Literal["job"] = Field(default="job")
    created_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: JobStatus
    links: dict[str, str] = Field(default_factory=dict)
    errors: list[ErrorDetail] = []
    globals: dict[GlobalVarKey, GlobalVarValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def build_links(self) -> WorkflowJobResponse:
        """Automatically populate links for the client."""
        if not self.links:
            self.links = {
                "status": f"/api/v2/workflows?job_id={self.job_id!s}",
                "events": f"/api/v2/workflows/{self.job_id!s}/events",
                "stop": "/api/v2/workflows/stop",
            }
        return self


class WorkflowStreamEvent(BaseModel):
    """Streaming event response."""

    type: str
    run_id: str
    timestamp: int
    raw_event: dict[str, Any]


class WorkflowStopRequest(BaseModel):
    """Request schema for stopping workflow."""

    job_id: JobId


class WorkflowStopResponse(BaseModel):
    """Response schema for stopping workflow."""

    job_id: JobId
    message: str | None = None


# OpenAPI response definitions
WORKFLOW_EXECUTION_RESPONSES = {
    200: {
        "description": "Workflow execution response",
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        WorkflowExecutionResponse.model_json_schema(),
                        WorkflowJobResponse.model_json_schema(),
                    ],
                    "discriminator": {
                        "propertyName": "object",
                        "mapping": {
                            "response": "#/components/schemas/WorkflowExecutionResponse",
                            "job": "#/components/schemas/WorkflowJobResponse",
                        },
                    },
                }
            },
            "text/event-stream": {
                "schema": WorkflowStreamEvent.model_json_schema(),
                "description": "Server-sent events for streaming execution",
            },
        },
    }
}

WORKFLOW_STATUS_RESPONSES = {
    200: {
        "description": "Workflow status response",
        "content": {
            "application/json": {"schema": WorkflowExecutionResponse.model_json_schema()},
            "text/event-stream": {
                "schema": WorkflowStreamEvent.model_json_schema(),
                "description": "Server-sent events for streaming status",
            },
        },
    }
}
