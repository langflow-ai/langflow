from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_serializer
from typing_extensions import TypedDict

from langflow.schema.encoders import CUSTOM_ENCODERS


class HeaderDict(TypedDict, total=False):
    title: str | None
    icon: str | None


class BaseContent(BaseModel):
    """Base class for all content types."""

    type: str = Field(..., description="Type of the content")
    duration: int | None = None
    header: HeaderDict | None = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseContent":
        return cls(**data)

    @model_serializer(mode="wrap")
    def serialize_model(self, nxt) -> dict[str, Any]:
        try:
            dump = nxt(self)
            return jsonable_encoder(dump, custom_encoder=CUSTOM_ENCODERS)
        except Exception:  # noqa: BLE001
            return nxt(self)


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
    duration: int | None = None


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

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["tool_use"] = Field(default="tool_use")
    name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict, alias="input")
    output: Any | None = None
    error: Any | None = None
    duration: int | None = None
