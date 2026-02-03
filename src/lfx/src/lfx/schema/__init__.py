"""Schema modules for lfx package."""

__all__ = [
    "WORKFLOW_EXECUTION_RESPONSES",
    "WORKFLOW_STATUS_RESPONSES",
    "ComponentOutput",
    "Data",
    "DataFrame",
    "ErrorDetail",
    "InputValue",
    "JobStatus",
    "Message",
    "OpenAIErrorResponse",
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponsesStreamChunk",
    "Tweaks",
    "UUIDstr",
    "WorkflowExecutionRequest",
    "WorkflowExecutionResponse",
    "WorkflowJobResponse",
    "WorkflowStopRequest",
    "WorkflowStopResponse",
    "WorkflowStreamEvent",
    "dotdict",
]


def __getattr__(name: str):
    # Import to avoid circular dependencies
    if name == "Data":
        from .data import Data

        return Data
    if name == "DataFrame":
        from .dataframe import DataFrame

        return DataFrame
    if name == "dotdict":
        from .dotdict import dotdict

        return dotdict
    if name == "InputValue":
        from .graph import InputValue

        return InputValue
    if name == "Tweaks":
        from .graph import Tweaks

        return Tweaks
    if name == "Message":
        from .message import Message

        return Message
    if name == "UUIDstr":
        from .serialize import UUIDstr

        return UUIDstr
    if name == "OpenAIResponsesRequest":
        from .openai_responses_schemas import OpenAIResponsesRequest

        return OpenAIResponsesRequest
    if name == "OpenAIResponsesResponse":
        from .openai_responses_schemas import OpenAIResponsesResponse

        return OpenAIResponsesResponse
    if name == "OpenAIResponsesStreamChunk":
        from .openai_responses_schemas import OpenAIResponsesStreamChunk

        return OpenAIResponsesStreamChunk
    if name == "OpenAIErrorResponse":
        from .openai_responses_schemas import OpenAIErrorResponse

        return OpenAIErrorResponse
    if name == "WorkflowExecutionRequest":
        from .workflow import WorkflowExecutionRequest

        return WorkflowExecutionRequest
    if name == "WorkflowExecutionResponse":
        from .workflow import WorkflowExecutionResponse

        return WorkflowExecutionResponse
    if name == "WorkflowJobResponse":
        from .workflow import WorkflowJobResponse

        return WorkflowJobResponse
    if name == "WorkflowStreamEvent":
        from .workflow import WorkflowStreamEvent

        return WorkflowStreamEvent
    if name == "WORKFLOW_EXECUTION_RESPONSES":
        from .workflow import WORKFLOW_EXECUTION_RESPONSES

        return WORKFLOW_EXECUTION_RESPONSES
    if name == "WORKFLOW_STATUS_RESPONSES":
        from .workflow import WORKFLOW_STATUS_RESPONSES

        return WORKFLOW_STATUS_RESPONSES
    if name == "WorkflowStopRequest":
        from .workflow import WorkflowStopRequest

        return WorkflowStopRequest
    if name == "WorkflowStopResponse":
        from .workflow import WorkflowStopResponse

        return WorkflowStopResponse
    if name == "JobStatus":
        from .workflow import JobStatus

        return JobStatus
    if name == "ErrorDetail":
        from .workflow import ErrorDetail

        return ErrorDetail
    if name == "ComponentOutput":
        from .workflow import ComponentOutput

        return ComponentOutput

    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
