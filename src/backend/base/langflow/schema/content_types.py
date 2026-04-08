from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
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


class _MediaContentMixin:
    """Shared validation for media content types (image, audio, video)."""

    @model_validator(mode="after")
    def _validate_media_source(self):
        if not self.urls and not self.base64:
            msg = f"{type(self).__name__} requires at least one of 'urls' or 'base64'"
            raise ValueError(msg)
        if self.base64 and not self.mime_type:
            msg = f"{type(self).__name__} with 'base64' data requires 'mime_type'"
            raise ValueError(msg)
        return self


class ImageContent(_MediaContentMixin, BaseContent):
    """Content type for image content."""

    type: Literal["image"] = Field(default="image")
    urls: list[str] | None = None
    base64: str | None = None
    mime_type: str | None = None
    caption: str | None = None


class AudioContent(_MediaContentMixin, BaseContent):
    """Content type for audio content."""

    type: Literal["audio"] = Field(default="audio")
    urls: list[str] | None = None
    base64: str | None = None
    mime_type: str | None = None
    transcript: str | None = None


class VideoContent(_MediaContentMixin, BaseContent):
    """Content type for video content."""

    type: Literal["video"] = Field(default="video")
    urls: list[str] | None = None
    base64: str | None = None
    mime_type: str | None = None


class FileContent(BaseContent):
    """Content type for file content."""

    type: Literal["file"] = Field(default="file")
    urls: list[str] | None = None
    mime_type: str | None = None
    filename: str | None = None

    @model_validator(mode="after")
    def _validate_file_source(self):
        if not self.urls:
            msg = "FileContent requires 'urls'"
            raise ValueError(msg)
        return self


class ReasoningContent(BaseContent):
    """Content type for reasoning content."""

    type: Literal["reasoning"] = Field(default="reasoning")
    text: str = ""


class UsageContent(BaseContent):
    """Content type for usage/token tracking content."""

    type: Literal["usage"] = Field(default="usage")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    model: str | None = None


class CitationContent(BaseContent):
    """Content type for citation content."""

    type: Literal["citation"] = Field(default="citation")
    url: str | None = None
    title: str | None = None
    cited_text: str | None = None
    start_index: int | None = Field(default=None, ge=0)
    end_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_index_range(self):
        if self.start_index is not None and self.end_index is not None and self.start_index > self.end_index:
            msg = f"start_index ({self.start_index}) must be <= end_index ({self.end_index})"
            raise ValueError(msg)
        return self
