from typing import Annotated

from pydantic import BaseModel, Field

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
