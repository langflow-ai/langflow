"""Request and response schemas for the Assistant API."""

from typing import Literal

from lfx.services.deps import get_settings_service
from pydantic import BaseModel, Field, field_validator

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


def _reject_overlong_message(value: str | None) -> str | None:
    """Enforce ``LANGFLOW_ASSISTANT_MAX_MESSAGE_LENGTH`` on an assistant prompt.

    Checked at request time rather than as a static ``max_length`` so the limit stays a single
    operator-tunable number shared with the UI (mirrored through ``/api/v1/config``); a static
    schema bound would drift from whatever the deployment configured.
    """
    if value is None:
        return value
    limit = get_settings_service().settings.assistant_max_message_length
    if len(value) > limit:
        msg = f"Message is too long: {len(value)} characters, limit is {limit}."
        raise ValueError(msg)
    return value


class AssistantRequest(BaseModel):
    """Request model for assistant interactions."""

    flow_id: str
    component_id: str | None = None
    field_name: str | None = None
    input_value: str | None = None
    max_retries: int | None = Field(None, ge=1, le=5)
    model_name: str | None = None
    provider: str | None = None
    session_id: str | None = None
    history_limit: int | None = Field(None, ge=0, le=100)
    iterations_limit: int | None = Field(None, ge=1, le=200)

    @field_validator("input_value")
    @classmethod
    def check_input_value_length(cls, value: str | None) -> str | None:
        return _reject_overlong_message(value)


class HeadlessAssistantRequest(BaseModel):
    """Request model for the headless (auto-apply) assistant route.

    Unlike ``AssistantRequest`` the flow is optional (one is created when absent)
    and the caller is not a UI, so there is no component/field review context.
    """

    instruction: str
    flow_id: str | None = None
    provider: str | None = None
    model_name: str | None = None
    session_id: str | None = None

    @field_validator("instruction")
    @classmethod
    def check_instruction_length(cls, value: str) -> str:
        _reject_overlong_message(value)
        return value


class ValidationResult(BaseModel):
    """Result of component code validation."""

    is_valid: bool
    code: str | None = None
    error: str | None = None
    class_name: str | None = None
