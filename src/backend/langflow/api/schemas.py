from typing import Any, Union
from pydantic import BaseModel, validator


class ChatMessage(BaseModel):
    """Chat message schema."""

    is_bot: bool = False
    message: Union[str, None] = None
    type: str = "human"


class ChatResponse(ChatMessage):
    """Chat response schema."""

    intermediate_steps: str
    type: str
    is_bot: bool = True
    files: list = []

    @validator("type")
    def validate_message_type(cls, v):
        if v not in ["start", "stream", "end", "error", "info", "file"]:
            raise ValueError("type must be start, stream, end, error, info, or file")
        return v


class FileResponse(ChatMessage):
    """File response schema."""

    data: Any
    data_type: str
    type: str = "file"
    is_bot: bool = True

    @validator("data_type")
    def validate_data_type(cls, v):
        if v not in ["image", "csv"]:
            raise ValueError("data_type must be image or csv")
        return v
