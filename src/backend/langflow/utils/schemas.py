from typing import Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: Union[str, List[Union[str, Dict]]]
    sender: Optional[str] = "Machine"
    sender_name: Optional[str] = "AI"

    @classmethod
    def from_message(cls, message: BaseMessage, sender: Optional[str] = "Machine", sender_name: Optional[str] = "AI"):
        """Build chat output response from message."""
        content = message.content
        return cls(message=content, sender=sender, sender_name=sender_name)
