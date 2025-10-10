import inspect
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ErrorContent
from lfx.schema.properties import Properties
from lfx.schema.validators import timestamp_to_str_validator
from lfx.utils.constants import MESSAGE_SENDER_USER
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class PlaygroundEvent(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    properties: Properties | None = Field(default=None)
    sender_name: str | None = Field(default=None)
    content_blocks: list[ContentBlock] | None = Field(default=None)
    format_type: Literal["default", "error", "warning", "info"] = Field(default="default")
    files: list[str] | None = Field(default=None)
    text: str | None = Field(default=None)
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )
    id_: UUID | str | None = Field(default=None, alias="id")

    @field_serializer("timestamp")
    @classmethod
    def serialize_timestamp(cls, v: str) -> str:
        return v

    @field_validator("id_")
    @classmethod
    def validate_id(cls, v: UUID | str | None) -> str | None:
        if isinstance(v, UUID):
            return str(v)
        return v


class MessageEvent(PlaygroundEvent):
    category: Literal["message", "error", "warning", "info"] = "message"
    format_type: Literal["default", "error", "warning", "info"] = Field(default="default")
    session_id: str | None = Field(default=None)
    error: bool = Field(default=False)
    edit: bool = Field(default=False)
    flow_id: UUID | str | None = Field(default=None)
    sender: str = Field(default=MESSAGE_SENDER_USER)
    sender_name: str = Field(default="User")

    @field_validator("flow_id")
    @classmethod
    def validate_flow_id(cls, v: UUID | str | None) -> str | None:
        if isinstance(v, UUID):
            return str(v)
        return v


class ErrorEvent(MessageEvent):
    background_color: str = Field(default="#FF0000")
    text_color: str = Field(default="#FFFFFF")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="error")
    allow_markdown: bool = Field(default=False)
    category: Literal["error"] = "error"


class WarningEvent(PlaygroundEvent):
    background_color: str = Field(default="#FFA500")
    text_color: str = Field(default="#000000")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="warning")


class InfoEvent(PlaygroundEvent):
    background_color: str = Field(default="#0000FF")
    text_color: str = Field(default="#FFFFFF")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="info")


class TokenEvent(BaseModel):
    chunk: str = Field(...)
    id: UUID | str | None = Field(alias="id")
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )


# Factory functions first
def create_message(
    text: str,
    category: Literal["message", "error", "warning", "info"] = "message",
    properties: dict | None = None,
    content_blocks: list[ContentBlock] | None = None,
    sender_name: str | None = None,
    files: list[str] | None = None,
    timestamp: str | None = None,
    format_type: Literal["default", "error", "warning", "info"] = "default",
    sender: str | None = None,
    session_id: str | None = None,
    id: UUID | str | None = None,  # noqa: A002
    flow_id: UUID | str | None = None,
    *,
    error: bool = False,
    edit: bool = False,
) -> MessageEvent:
    return MessageEvent(
        text=text,
        properties=properties,
        category=category,
        content_blocks=content_blocks,
        sender_name=sender_name,
        files=files,
        timestamp=timestamp,
        format_type=format_type,
        sender=sender,
        id=id,
        session_id=session_id,
        error=error,
        edit=edit,
        flow_id=flow_id,
    )


def create_error(
    text: str,
    properties: dict | None = None,
    traceback: str | None = None,
    title: str = "Error",
    timestamp: str | None = None,
    id: UUID | str | None = None,  # noqa: A002
    flow_id: UUID | str | None = None,
    session_id: str | None = None,
    content_blocks: list[ContentBlock] | None = None,
) -> ErrorEvent:
    if traceback:
        content_blocks = content_blocks or []
        content_blocks += [ContentBlock(title=title, contents=[ErrorContent(type="error", traceback=traceback)])]
    return ErrorEvent(
        text=text,
        properties=properties,
        content_blocks=content_blocks,
        timestamp=timestamp,
        id=id,
        flow_id=flow_id,
        session_id=session_id,
    )


def create_warning(message: str) -> WarningEvent:
    return WarningEvent(text=message)


def create_info(message: str) -> InfoEvent:
    return InfoEvent(text=message)


def create_token(chunk: str, id: str) -> TokenEvent:  # noqa: A002
    return TokenEvent(
        chunk=chunk,
        id=id,
    )


_EVENT_CREATORS: dict[str, tuple[Callable, inspect.Signature]] = {
    "message": (create_message, inspect.signature(create_message)),
    "error": (create_error, inspect.signature(create_error)),
    "warning": (create_warning, inspect.signature(create_warning)),
    "info": (create_info, inspect.signature(create_info)),
    "token": (create_token, inspect.signature(create_token)),
}


def create_event_by_type(event_type: str, **kwargs) -> PlaygroundEvent | dict:
    if event_type not in _EVENT_CREATORS:
        return kwargs
    try:
        creator_func, signature = _EVENT_CREATORS[event_type]
    except KeyError as e:
        msg = f"Invalid event type: {event_type}"
        raise ValueError(msg) from e
    valid_params = {k: v for k, v in kwargs.items() if k in signature.parameters}
    return creator_func(**valid_params)
