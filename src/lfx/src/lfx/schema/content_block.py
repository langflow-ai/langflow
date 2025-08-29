from typing import Annotated

from pydantic import BaseModel, Discriminator, Field, Tag, field_serializer, field_validator
from typing_extensions import TypedDict

from .content_types import CodeContent, ErrorContent, JSONContent, MediaContent, TextContent, ToolContent


def _get_type(d: dict | BaseModel) -> str | None:
    if isinstance(d, dict):
        return d.get("type")
    return getattr(d, "type", None)


# Create a union type of all content types
ContentType = Annotated[
    Annotated[ToolContent, Tag("tool_use")]
    | Annotated[ErrorContent, Tag("error")]
    | Annotated[TextContent, Tag("text")]
    | Annotated[MediaContent, Tag("media")]
    | Annotated[CodeContent, Tag("code")]
    | Annotated[JSONContent, Tag("json")],
    Discriminator(_get_type),
]


class ContentBlock(BaseModel):
    """A block of content that can contain different types of content."""

    title: str
    contents: list[ContentType]
    allow_markdown: bool = Field(default=True)
    media_url: list[str] | None = None

    def __init__(self, **data) -> None:
        super().__init__(**data)
        schema_dict = self.__pydantic_core_schema__["schema"]
        if "fields" in schema_dict:
            fields = schema_dict["fields"]
        elif "schema" in schema_dict:
            fields = schema_dict["schema"]["fields"]
        fields_with_default = (f for f, d in fields.items() if "default" in d["schema"])
        self.model_fields_set.update(fields_with_default)

    @field_validator("contents", mode="before")
    @classmethod
    def validate_contents(cls, v) -> list[ContentType]:
        if isinstance(v, dict):
            msg = "Contents must be a list of ContentTypes"
            raise TypeError(msg)
        return [v] if isinstance(v, BaseModel) else v

    @field_serializer("contents")
    def serialize_contents(self, value) -> list[dict]:
        return [v.model_dump() for v in value]


class ContentBlockDict(TypedDict):
    title: str
    contents: list[dict]
    allow_markdown: bool
    media_url: list[str] | None
