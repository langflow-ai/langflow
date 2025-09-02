"""Schema modules for lfx package."""

__all__ = [
    "Data",
    "DataFrame",
    "InputValue",
    "Message",
    "OpenAIErrorResponse",
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponsesStreamChunk",
    "Tweaks",
    "UUIDstr",
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

    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
