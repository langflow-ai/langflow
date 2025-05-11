from pydantic import BaseModel, Field, field_validator
from typing import Any

class ChatMessage(BaseModel):
    is_bot: bool = False
    message: str | None | dict = None
    chat_key: str | None = Field(None, serialization_alias="chatKey")
    type: str = "human"

class ChatResponse(ChatMessage):
    intermediate_steps: str
    type: str
    is_bot: bool = True
    files: list = []

    @field_validator("type")
    @classmethod
    def validate_message_type(cls, v):
        if v not in {"start", "stream", "end", "error", "info", "file"}:
            msg = "type must be start, stream, end, error, info, or file"
            raise ValueError(msg)
        return v

class PromptResponse(ChatMessage):
    prompt: str
    type: str = "prompt"
    is_bot: bool = True

class FileResponse(ChatMessage):
    data: Any = None
    data_type: str
    type: str = "file"
    is_bot: bool = True

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v not in {"image", "csv"}:
            msg = "data_type must be image or csv"
            raise ValueError(msg)
        return v
