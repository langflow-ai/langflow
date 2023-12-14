from typing import Optional

from pydantic import BaseModel


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: str
    sender: Optional[str] = "Machine"
    sender_name: Optional[str] = "AI"
