from typing import Annotated

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .content_types import ContentTypes

# Create a union type of all content types
ContentType = Annotated[
    ContentTypes,
    Field(discriminator="type"),
]


class ContentBlock(BaseModel):
    """A block of content that can contain different types of content."""

    title: str
    content: ContentType
    allow_markdown: bool = Field(default=True)
    media_url: list[str] | None = None

    def __init__(self, **data) -> None:
        super().__init__(**data)
        fields = self.__pydantic_core_schema__["schema"]["fields"]
        fields_with_default = (f for f, d in fields.items() if "default" in d["schema"])
        self.model_fields_set.update(fields_with_default)


class ContentBlockDict(TypedDict):
    title: str
    content: ContentType
    allow_markdown: bool
    media_url: list[str] | None
