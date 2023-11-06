from pydantic import BaseModel


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: str
    is_ai: bool = True
