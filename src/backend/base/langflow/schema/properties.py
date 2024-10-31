from pydantic import BaseModel


class Properties(BaseModel):
    text_color: str | None = None
    background_color: str | None = None
    edited: bool = False
    source: str | None = None
    source_display_name: str | None = None
    icon: str | None = None
    allow_markdown: bool = False
    targets: list = []
