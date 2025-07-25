"""LFX API v1 schemas."""

from typing import Literal

from pydantic import BaseModel, Field

InputType = Literal["chat", "text", "any"]


class InputValueRequest(BaseModel):
    """Request model for input values."""

    components: list[str] | None = []
    input_value: str | None = None
    session: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )
