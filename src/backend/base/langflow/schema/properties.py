from pydantic import BaseModel, Field, field_validator


class Source(BaseModel):
    id: str = Field(default="", description="The id of the source component.")
    display_name: str = Field(default="", description="The display name of the source component.")
    source: str = Field(
        default="",
        description="The source of the message. Normally used to display the model name (e.g. 'gpt-4o')",
    )


class Properties(BaseModel):
    text_color: str | None = None
    background_color: str | None = None
    edited: bool = False
    source: Source = Field(default_factory=Source)
    icon: str | None = None
    allow_markdown: bool = False
    targets: list = []

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v):
        if isinstance(v, str):
            return Source(id=v, display_name=v, source=v)
        return v
