from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field

from langflow.schema.validators import timestamp_to_str_validator


class BaseContent(BaseModel):
    """Base class for all content types."""

    type: str = Field(..., description="Type of the content")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseContent":
        return cls(**data)


class ErrorContent(BaseContent):
    """Content type for error messages."""

    type: Literal["error"] = Field(default="error")
    component: str | None = None
    field: str | None = None
    reason: str | None = None
    solution: str | None = None
    traceback: str | None = None


class TextContent(BaseContent):
    """Content type for simple text content."""

    type: Literal["text"] = Field(default="text")
    text: str


class MediaContent(BaseContent):
    """Content type for media content."""

    type: Literal["media"] = Field(default="media")
    urls: list[str]
    caption: str | None = None


class JSONContent(BaseContent):
    """Content type for JSON content."""

    type: Literal["json"] = Field(default="json")
    data: dict[str, Any]


class CodeContent(BaseContent):
    """Content type for code snippets."""

    type: Literal["code"] = Field(default="code")
    code: str
    language: str
    title: str | None = None


class ToolContent(BaseContent):
    """Content type for tool start content."""

    type: Literal["tool_use"] = Field(default="tool_use")
    name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict, alias="input")
    output: Any | None = None
    error: Any | None = None
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )


ContentTypes: TypeAlias = ToolContent | ErrorContent | TextContent | MediaContent | CodeContent | JSONContent
