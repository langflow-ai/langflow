from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from langflow.schema.content_block import ContentBlock
from langflow.schema.utils import timestamp_to_str_validator


class PlaygroundEvent(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    background_color: str = Field(default="#FFFFFF")
    text_color: str = Field(default="#000000")
    allow_markdown: bool = Field(default=True)
    icon: str | None = Field(default=None)
    sender_name: str | None = Field(default=None)
    content_blocks: list[ContentBlock] | None = Field(default=None)
    format_type: Literal["default", "error", "warning", "info"] = Field(default="default")
    files: list[str] | None = Field(default=None)
    text: str | None = Field(default=None)
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    id_: UUID | str | None = Field(alias="id")

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
    format_type: Literal["default", "error", "warning", "info"] = Field(default="default")
    session_id: str | None = Field(default=None)
    error: bool = Field(default=False)
    edit: bool = Field(default=False)
    flow_id: UUID | str | None = Field(default=None)

    @field_validator("flow_id")
    @classmethod
    def validate_flow_id(cls, v: UUID | str | None) -> str | None:
        if isinstance(v, UUID):
            return str(v)
        return v


class ErrorEvent(PlaygroundEvent):
    background_color: str = Field(default="#FF0000")
    text_color: str = Field(default="#FFFFFF")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="error")
    allow_markdown: bool = Field(default=False)


class WarningEvent(PlaygroundEvent):
    background_color: str = Field(default="#FFA500")
    text_color: str = Field(default="#000000")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="warning")


class InfoEvent(PlaygroundEvent):
    background_color: str = Field(default="#0000FF")
    text_color: str = Field(default="#FFFFFF")
    format_type: Literal["default", "error", "warning", "info"] = Field(default="info")


class TokenEvent(PlaygroundEvent):
    chunk: str = Field(...)
    sender: str = Field(...)
    sender_name: str = Field(...)
    id: UUID | str | None = Field(alias="id")


# Factory functions
def create_message(
    text: str,
    icon: str | None = None,
    background_color: str = "#FFFFFF",
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
    allow_markdown: bool = True,
    error: bool = False,
    edit: bool = False,
):
    return MessageEvent(
        text=text,
        icon=icon,
        background_color=background_color,
        content_blocks=content_blocks,
        allow_markdown=allow_markdown,
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


def create_error(error_message: str, traceback: str | None = None, title: str = "Error"):
    content_blocks = [ContentBlock(title=title, content=traceback)] if traceback else None
    return ErrorEvent(text=error_message, content_blocks=content_blocks)


def create_warning(message: str):
    return WarningEvent(text=message)


def create_info(message: str):
    return InfoEvent(text=message)


def create_token(chunk: str, text: str, sender: str, sender_name: str, id: str):  # noqa: A002
    return TokenEvent(
        chunk=chunk,
        text=text,
        sender=sender,
        sender_name=sender_name,
        id=id,
    )


def create_event_by_type(
    event_type: Literal["message", "error", "warning", "info", "token"], **kwargs
) -> PlaygroundEvent:
    if event_type == "message":
        return create_message(**kwargs)
    if event_type == "error":
        return create_error(**kwargs)
    if event_type == "warning":
        return create_warning(**kwargs)
    if event_type == "info":
        return create_info(**kwargs)
    if event_type == "token":
        return create_token(**kwargs)
    msg = f"Invalid event type: {event_type}"
    raise TypeError(msg)
