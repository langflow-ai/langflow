from typing import Annotated, Any

from pydantic import BaseModel, Field

from .content_types import CodeContent, ErrorContent, MediaContent, TextContent

# Create a union type of all content types
ContentType = Annotated[ErrorContent | TextContent | MediaContent | CodeContent, Field(discriminator="type")]


class ContentBlock(BaseModel):
    """A block of content that can contain different types of content."""

    title: str
    content: ContentType | str | dict[str, Any] | list[Any] = Field(
        ..., description="Content can be either a ContentType or primitive types for backward compatibility"
    )
    allow_markdown: bool = Field(default=True)
    media_url: list[str] | None = None
