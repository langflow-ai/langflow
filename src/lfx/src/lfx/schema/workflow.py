"""Workflow execution schemas for V2 API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

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
    content: Any | None = None
    metadata: dict[str, Any] | None = None


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


class WorkflowExecutionResponse(BaseModel):
    """Synchronous workflow execution response."""

    flow_id: str
    job_id: JobId | None = None
    object: Literal["response"] = Field(default="response")
    created_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: JobStatus
    errors: list[ErrorDetail] = []
    inputs: dict[str, Any] = {}
    globals: dict[GlobalVarKey, GlobalVarValue] = Field(default_factory=dict)
    outputs: dict[str, ComponentOutput] = {}


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
