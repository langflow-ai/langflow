"""Content types for ``Message.content_blocks``.

Each content type carries one kind of payload — text, a tool call, an image,
a chain-of-thought trace, etc. — and the ``contents`` field on ``BaseContent``
lets any node nest more content underneath. That nesting is how a single
``ToolContent`` can carry a multimodal result (text + image + citation), a
``ReasoningContent`` can carry sub-steps, and a ``ContentBlock`` can be a
titled group of related items, all using the same primitive.

``ContentType`` is a discriminated union over every concrete subclass
(including ``ContentBlock``), keyed by the ``type`` literal on each class.
A ``content_blocks`` list is always ``list[ContentType]`` — there's no
separate "wrapper" shape; the wrapper *is* a ContentType.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)
from typing_extensions import TypedDict

from langflow.schema.encoders import CUSTOM_ENCODERS


class HeaderDict(TypedDict, total=False):
    title: str | None
    icon: str | None


class BaseContent(BaseModel):
    """Base class for all content types.

    The optional ``id`` field carries stable identity across re-emissions of
    the same logical block. Producers that have a natural id (LangChain
    ``tool_call_id``, an external API id, a UUID stamped before the first
    emission) set it; consumers use it for dedup and cross-frame correlation.
    Without an id, consumers fall back to position-derived dedup, which
    assumes ``content_blocks`` is append-only within a message lifetime.

    The optional ``contents`` field lets any content type nest more content
    underneath. Leaf types (``TextContent``, ``ErrorContent``, ``UsageContent``)
    leave it empty; container-shaped types (``ContentBlock``, multimodal
    ``ToolContent``, multi-step ``ReasoningContent``) populate it.
    """

    type: str = Field(..., description="Type of the content")
    id: str | None = Field(
        default=None,
        description=(
            "Optional stable identity for this content block across "
            "re-emissions. Set by producers that have a natural id "
            "(e.g. LangChain tool_call_id)."
        ),
    )
    duration: int | None = None
    header: HeaderDict | None = Field(default_factory=dict)
    contents: list[ContentType] = Field(
        default_factory=list,
        description=(
            "Nested content. Leaf types leave this empty; container-shaped "
            "types (groups, multimodal tool outputs, multi-step reasoning) "
            "populate it."
        ),
    )

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Mark only the discriminator as "set" so partial-update callers using
        # ``model_dump(exclude_unset=True)`` (notably ``aupdate_messages``)
        # keep the ``type`` tag. Without it, ``TextContent(text="x")`` would
        # dump to ``{"text": "x"}`` and the next read-back through
        # ``MessageRead``'s discriminated union would fail with
        # ``union_tag_not_found``. Other defaulted fields stay unset so true
        # exclude_unset semantics survive: a patch like ``ContentBlock(title=
        # "...")`` no longer overwrites an existing block's ``duration`` /
        # ``header`` / ``contents`` with their defaults on merge.
        self.model_fields_set.add("type")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseContent:
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
    """Content type for a tool invocation.

    ``output`` carries a string / JSON output (legacy / single-value tools).
    Rich, multimodal outputs use the inherited ``contents`` list — e.g. an
    image-generation tool returns
    ``ToolContent(name=..., contents=[TextContent(...), ImageContent(...)])``.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["tool_use"] = Field(default="tool_use")
    name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict, alias="input")
    output: Any | None = None
    error: Any | None = None
    duration: int | None = None

    @field_validator("tool_input", mode="before")
    @classmethod
    def _coerce_tool_input(cls, v: Any) -> dict[str, Any]:
        # LangChain ``AgentAction.tool_input`` is ``str | dict`` during
        # streaming, and ``event["data"].get("input") or {}`` passes a
        # non-empty string straight through. The dict-typed field used to
        # raise ValidationError on it. Parse JSON objects; wrap any other
        # string under an ``input`` key so the field always validates.
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except (ValueError, TypeError):
                return {"input": v}
            return parsed if isinstance(parsed, dict) else {"input": parsed}
        if v is None:
            return {}
        return v


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


class ContentBlock(BaseContent):
    """A titled group of nested contents.

    Use this when a section needs an explicit label and icon — typically
    errors, agent step traces, or any UI grouping that shouldn't be inferred
    from adjacency. The ``contents`` list (inherited from ``BaseContent``)
    holds the grouped items.
    """

    type: Literal["group"] = Field(default="group")
    title: str
    allow_markdown: bool = Field(default=True)
    media_url: list[str] | None = None

    # ``__init__`` is inherited from ``BaseContent``: it marks only the
    # ``type`` discriminator as set, so ``model_dump(exclude_unset=True)``
    # preserves ``type="group"`` while leaving ``allow_markdown`` and the
    # other defaulted fields out of partial-update merges.

    @field_validator("contents", mode="before")
    @classmethod
    def validate_contents(cls, v):
        # Accept either a single content item or a list. Legacy callers may
        # pass a bare BaseModel; wrap it so the discriminated-union validator
        # downstream sees a list.
        if isinstance(v, dict):
            msg = "Contents must be a list of ContentTypes"
            raise TypeError(msg)
        return [v] if isinstance(v, BaseModel) else v

    @field_serializer("contents")
    def serialize_contents(self, value) -> list[dict]:
        return [v.model_dump() for v in value]


def _get_content_type(d: dict | BaseModel) -> str | None:
    """Pydantic discriminator: return the ``type`` field from dict or model."""
    if isinstance(d, dict):
        return d.get("type")
    return getattr(d, "type", None)


# Discriminated union over every concrete content type. ``ContentBlock`` is a
# first-class member (tag ``group``) so consumers walk one uniform shape
# instead of branching on "wrapper vs leaf."
ContentType = Annotated[
    Annotated[ToolContent, Tag("tool_use")]
    | Annotated[ErrorContent, Tag("error")]
    | Annotated[TextContent, Tag("text")]
    | Annotated[MediaContent, Tag("media")]
    | Annotated[CodeContent, Tag("code")]
    | Annotated[JSONContent, Tag("json")]
    | Annotated[ImageContent, Tag("image")]
    | Annotated[AudioContent, Tag("audio")]
    | Annotated[VideoContent, Tag("video")]
    | Annotated[FileContent, Tag("file")]
    | Annotated[ReasoningContent, Tag("reasoning")]
    | Annotated[UsageContent, Tag("usage")]
    | Annotated[CitationContent, Tag("citation")]
    | Annotated[ContentBlock, Tag("group")],
    Discriminator(_get_content_type),
]


# Resolve the forward reference on ``BaseContent.contents``. Every subclass
# inherits the field, so rebuilding the parent is enough — Pydantic re-derives
# the validator schema for subclasses on next validation.
BaseContent.model_rebuild()


class ContentBlockDict(TypedDict):
    """Legacy TypedDict shape kept for callers that expect a plain dict."""

    title: str
    contents: list[dict]
    allow_markdown: bool
    media_url: list[str] | None
