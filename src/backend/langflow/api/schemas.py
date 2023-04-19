from typing import Any
from pydantic import BaseModel, validator


class ChatMessage(BaseModel):
    """Chat message schema."""

    sender: str
    message: str

    @validator("sender")
    def sender_must_be_bot_or_you(cls, v):
        if v not in ["bot", "you"]:
            raise ValueError("sender must be bot or you")
        return v


class ChatResponse(ChatMessage):
    """Chat response schema."""

    intermediate_steps: str
    type: str
    data: Any = None

    @validator("type")
    def validate_message_type(cls, v):
        if v not in ["start", "stream", "end", "error", "info"]:
            raise ValueError("type must be start, stream, end, error or info")
        return v
