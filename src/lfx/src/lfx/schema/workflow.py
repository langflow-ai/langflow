"""Workflow execution schemas for V2 API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    job_id: str | None = None
    object: Literal["response"] = Field(default="response")
    created_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: JobStatus
    errors: list[ErrorDetail] = []
    inputs: dict[str, Any] = {}
    outputs: dict[str, ComponentOutput] = {}


class WorkflowJobResponse(BaseModel):
    """Background job response."""

    job_id: str
    flow_id: str
    object: Literal["job"] = Field(default="job")
    created_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: JobStatus
    links: dict[str, str] = Field(default_factory=dict)
    errors: list[ErrorDetail] = []

    @model_validator(mode="after")
    def build_links(self) -> WorkflowJobResponse:
        """Automatically populate links for the client."""
        if not self.links:
            self.links = {
                "status": f"/api/v2/workflows?job_id={self.job_id}",
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

    job_id: str
    force: bool = Field(default=False, description="Force stop the workflow")


class WorkflowStopResponse(BaseModel):
    """Response schema for stopping workflow."""

    job_id: str
    status: Literal["stopped", "stopping", "not_found", "error"]
    message: str


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
