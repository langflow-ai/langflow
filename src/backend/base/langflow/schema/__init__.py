from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.openai_responses_schemas import (
    OpenAIErrorResponse,
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesStreamChunk,
)
from lfx.schema.serialize import UUIDstr

__all__ = [
    "Data",
    "DataFrame",
    "Message",
    "OpenAIErrorResponse",
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponsesStreamChunk",
    "UUIDstr",
    "dotdict",
]


def __getattr__(name: str):
    if name == "DataFrame":
        from lfx.schema.dataframe import DataFrame

        globals()["DataFrame"] = DataFrame
        return DataFrame
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
