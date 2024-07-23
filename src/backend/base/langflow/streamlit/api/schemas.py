from typing import Optional
from pydantic import BaseModel, Field


class ChatModel(BaseModel):
    welcome_msg: str = "Hello human, welcome to the digital world. Feel free to ask questions; I am ready to help you."
    write_speed: float = 0.05
    input_msg: str = "Ask some question..."
    ai_avatar: Optional[str] = None
    user_avatar: Optional[str] = None
    port: int = 5001


class ChatMessageModel(BaseModel):
    role: str
    content: str
    type: str = Field("text", pattern="text|image")
