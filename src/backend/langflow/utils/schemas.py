from pydantic import BaseModel
from typing import Optional


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: str
    sender: Optional[str] = "Machine"
    sender_name: Optional[str] = "AI"
