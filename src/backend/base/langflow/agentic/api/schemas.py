"""Request and response schemas for the Assistant API."""

from typing import Literal

from pydantic import BaseModel, Field

# All possible step types for SSE progress events
StepType = Literal[
    "generating",  # LLM is generating response
    "generating_component",  # LLM is generating component code
    "generating_plan",  # LLM is drafting a plan (precedes propose_plan / build_flow)
    "generating_flow",  # LLM is building a flow
    "orchestrating",  # Single agent loop working a multi-ask request (component + flow + run)
    "generation_complete",  # LLM finished generating
    "extracting_code",  # Extracting Python code from response
    "validating",  # Validating component code
    "validated",  # Validation succeeded
    "validation_failed",  # Validation failed
    "retrying",  # About to retry with error context
    "searching_components",  # Agent is searching for components
    "building_flow",  # Agent is building a flow from spec
    "flow_built",  # Flow built successfully
    "flow_build_failed",  # Flow build failed
    "flow_proposal_ready",  # Build-from-scratch flow ready, gated on user Continue/Dismiss
    "generating_document",  # Agent is materializing a file in the sandboxed workspace
    "document_ready",  # File write completed
]


class AssistantRequest(BaseModel):
    """Request model for assistant interactions."""

    flow_id: str
    component_id: str | None = None
    field_name: str | None = None
    input_value: str | None = Field(None, max_length=2000)
    max_retries: int | None = Field(None, ge=1, le=5)
    model_name: str | None = None
    provider: str | None = None
    session_id: str | None = None


class ValidationResult(BaseModel):
    """Result of component code validation."""

    is_valid: bool
    code: str | None = None
    error: str | None = None
    class_name: str | None = None
