from typing import Any, Union
from pydantic import BaseModel, validator


class ChatMessage(BaseModel):
    """Chat message schema."""

    sender: str
    message: Union[str, None] = None

    @validator("sender")
    def sender_must_be_bot_or_you(cls, v):
        if v not in ["bot", "you"]:
            raise ValueError("sender must be bot or you")
        return v


class ChatResponse(ChatMessage):
    """Chat response schema."""

    intermediate_steps: str
    type: str

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

    @validator("data_type")
    def validate_data_type(cls, v):
        if v not in ["image", "csv"]:
            raise ValueError("data_type must be image or csv")
        return v
