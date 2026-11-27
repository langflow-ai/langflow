"""Standalone JSON models for the Langflow 1.14 backend Workflow API.

Response status and reason strings, and extra fields, are preserved for additive
server changes. These models do not implement the server's execution policies.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRunRequest(BaseModel):
    """A JSON workflow run; use the existing V1 stream method for SSE.

    Cross-mode field combinations and authorization are validated by the server.
    None values are omitted on the wire, matching other SDK request models.
    """

    model_config = ConfigDict(extra="forbid")

    flow_id: UUID | str
    input_value: str = ""
    session_id: str | None = None
    mode: Literal["sync", "background"] = "sync"
    tweaks: dict[str, Any] = Field(default_factory=dict)
    globals: dict[str, str] = Field(default_factory=dict)
    output_ids: list[str] | None = None
    data: dict[str, Any] | None = None
    files: list[str] | None = None
    start_component_id: str | None = None
    stop_component_id: str | None = None
    stream_protocol: str = "langflow"
    expose_graph_state: bool | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)


class _WorkflowResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class WorkflowErrorDetail(_WorkflowResponseModel):
    """An error embedded in a successful workflow response, not HTTP detail."""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


class WorkflowOutput(_WorkflowResponseModel):
    """Primary answer disposition; an empty text string is a valid answer."""

    reason: str
    text: str | None = None
    source: str | None = None


class WorkflowComponentOutput(_WorkflowResponseModel):
    """One component's output, keyed by component ID in the parent outputs map."""

    type: str
    status: str
    display_name: str | None = None
    content: Any = None
    metadata: dict[str, Any] | None = None


class WorkflowExecutionResponse(_WorkflowResponseModel):
    """Full JSON execution result. All identities and timestamps come from the server."""

    object: Literal["response"]
    flow_id: str
    status: str
    created_timestamp: str
    output: WorkflowOutput
    has_errors: bool
    session_id: str | None = None
    job_id: str | None = None
    errors: list[WorkflowErrorDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    globals: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, WorkflowComponentOutput] = Field(default_factory=dict)
    human_request: dict[str, Any] | None = None


class WorkflowJobResponse(_WorkflowResponseModel):
    """A server job snapshot, including suspended jobs without a decision prompt."""

    object: Literal["job"]
    flow_id: str
    job_id: str
    status: str
    created_timestamp: str
    links: dict[str, str] = Field(default_factory=dict)
    errors: list[WorkflowErrorDetail] = Field(default_factory=list)
    globals: dict[str, str] = Field(default_factory=dict)


WorkflowExecutionResult = Annotated[
    WorkflowExecutionResponse | WorkflowJobResponse,
    Field(discriminator="object"),
]


class WorkflowStopResponse(_WorkflowResponseModel):
    """Acknowledgement only. Do not parse message text to infer a job status."""

    job_id: str
    message: str | None = None
