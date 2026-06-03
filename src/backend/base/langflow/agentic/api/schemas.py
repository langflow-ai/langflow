"""Request and response schemas for the Assistant API."""

from typing import Literal

from pydantic import BaseModel, Field

# All possible step types for SSE progress events
StepType = Literal[
    "generating",  # LLM is generating response
    "generating_component",  # LLM is generating component code
    "generating_flow",  # LLM is generating a complete flow
    "generation_complete",  # LLM finished generating
    "extracting_code",  # Extracting Python code from response
    "extracting_flow",  # Extracting compact flow JSON from response
    "validating",  # Validating component code
    "validating_flow",  # Validating compact flow against registry
    "validated",  # Validation succeeded
    "validated_flow",  # Flow validation passed
    "validation_failed",  # Validation failed
    "retrying",  # About to retry with error context
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
