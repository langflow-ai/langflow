"""Workflow execution schemas for V2 API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class ErrorDetail(BaseModel):
    """Error detail schema."""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


class ComponentOutput(BaseModel):
    """Component output schema."""

    type: str = Field(..., description="Type of the component output (e.g., 'message', 'data', 'tool', 'text')")
    component_id: str
    status: JobStatus
    content: Any | None = None
    metadata: dict[str, Any] | None = None


class GlobalInputs(BaseModel):
    """Global inputs that apply to all input components in the workflow."""

    input_value: str | None = Field(None, description="The input value to send to input components")
    input_type: str = Field("chat", description="The type of input (chat, text, etc.)")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")


class WorkflowExecutionRequest(BaseModel):
    """Request schema for workflow execution."""

    background: bool = False
    stream: bool = False
    flow_id: str
    inputs: dict[str, Any] | None = Field(
        None, description="Inputs with 'global' key for global inputs and component IDs for component-specific tweaks"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "background": False,
                    "stream": False,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {
                        "global": {
                            "input_value": "Hello, how can you help me today?",
                            "input_type": "chat",
                            "session_id": "session-123",
                        },
                        "llm_component": {"temperature": 0.7, "max_tokens": 100},
                        "opensearch_component": {"opensearch_url": "https://opensearch:9200"},
                    },
                },
                {
                    "background": True,
                    "stream": False,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {"global": {"input_value": "Process this in the background", "input_type": "text"}},
                },
                {
                    "background": False,
                    "stream": True,
                    "flow_id": "flow_67ccd2be17f0819081ff3bb2cf6508e60bb6a6b452d3795b",
                    "inputs": {"chat_component": {"text": "Stream this conversation"}},
                },
            ]
        },
        extra="forbid",
    )


class WorkflowExecutionResponse(BaseModel):
    """Synchronous workflow execution response."""

    flow_id: str
    job_id: str
    object: Literal["response"] = "response"
    created_timestamp: str
    status: JobStatus
    errors: list[ErrorDetail] = []
    inputs: dict[str, Any] = {}
    outputs: dict[str, ComponentOutput] = {}
    metadata: dict[str, Any] = {}


class WorkflowJobResponse(BaseModel):
    """Background job response."""

    job_id: str
    created_timestamp: str
    status: JobStatus
    errors: list[ErrorDetail] = []


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
                    ]
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
