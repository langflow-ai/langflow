"""Log schema and types for lfx package."""

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, field_serializer
from pydantic_core import PydanticSerializationError
from typing_extensions import Protocol

from lfx.schema.message import ContentBlock, Message
from lfx.serialization.serialization import serialize

# Simplified LoggableType without PlaygroundEvent dependency
LoggableType: TypeAlias = str | dict | list | int | float | bool | BaseModel | None


class LogFunctionType(Protocol):
    """Protocol for log function type."""

    def __call__(self, message: LoggableType | list[LoggableType], *, name: str | None = None) -> None: ...


class SendMessageFunctionType(Protocol):
    """Protocol for send message function type."""

    async def __call__(
        self,
        message: Message | None = None,
        text: str | None = None,
        background_color: str | None = None,
        text_color: str | None = None,
        icon: str | None = None,
        content_blocks: list[ContentBlock] | None = None,
        format_type: Literal["default", "error", "warning", "info"] = "default",
        id_: str | None = None,
        *,
        allow_markdown: bool = True,
        skip_db_update: bool = False,
    ) -> Message: ...


class OnTokenFunctionType(Protocol):
    """Protocol for on token function type."""

    def __call__(self, data: dict[str, Any]) -> None: ...


class Log(BaseModel):
    """Log model for storing log messages with serialization support."""

    name: str
    message: LoggableType
    type: str

    @field_serializer("message")
    def serialize_message(self, value):
        """Serialize the message field with fallback error handling."""
        try:
            return serialize(value)
        except UnicodeDecodeError:
            return str(value)  # Fallback to string representation
        except PydanticSerializationError:
            return str(value)  # Fallback to string for Pydantic errors
