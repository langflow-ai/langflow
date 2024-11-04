from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field


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


class ToolStartContent(BaseContent):
    """Content type for tool start content."""

    type: Literal["tool_start"] = Field(default="tool_start")
    tool_name: str
    tool_input: dict[str, Any]


class ToolEndContent(BaseContent):
    """Content type for tool end content."""

    type: Literal["tool_end"] = Field(default="tool_end")
    tool_name: str
    tool_output: Any


class ToolErrorContent(BaseContent):
    """Content type for tool error content."""

    type: Literal["tool_error"] = Field(default="tool_error")
    tool_name: str
    tool_error: str


ContentTypes: TypeAlias = (
    ToolStartContent
    | ToolEndContent
    | ToolErrorContent
    | ErrorContent
    | TextContent
    | MediaContent
    | CodeContent
    | JSONContent
)
