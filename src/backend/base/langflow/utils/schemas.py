import enum
from typing import Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, model_validator


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: Union[str, List[Union[str, Dict]]]
    sender: Optional[str] = "Machine"
    sender_name: Optional[str] = "AI"
    session_id: Optional[str] = None
    stream_url: Optional[str] = None
    component_id: Optional[str] = None

    @classmethod
    def from_message(
        cls,
        message: BaseMessage,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
    ):
        """Build chat output response from message."""
        content = message.content
        return cls(message=content, sender=sender, sender_name=sender_name)

    @model_validator(mode="after")
    def validate_message(self):
        """Validate message."""
        # The idea here is ensure the \n in message
        # is compliant with markdown if sender is machine
        # so, for example:
        # \n\n -> \n\n
        # \n -> \n\n

        if self.sender != "Machine":
            return self

        # We need to make sure we don't duplicate \n
        # in the message
        message = self.message.replace("\n\n", "\n")
        self.message = message.replace("\n", "\n\n")
        return self


class RecordOutputResponse(BaseModel):
    """Record output response schema."""

    records: List[Optional[Dict]]


class ContainsEnumMeta(enum.EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True
