from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ConfigDict, Field, field_serializer, field_validator

from lfx.schema.data import Data
from lfx.schema.properties import Properties
from lfx.utils.schemas import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


def timestamp_to_str_validator(value: Any) -> str:
    """Simple timestamp validator for base Message class."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S %Z")
    return str(value)


class Message(Data):
    """Base Message class for lfx package.

    This is a lightweight version with core functionality only.
    The enhanced version with complex dependencies is in langflow.schema.message_enhanced.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core fields
    text_key: str = "text"
    text: str | AsyncIterator | Iterator | None = Field(default="")
    sender: str | None = None
    sender_name: str | None = None
    files: list[str] | None = Field(default=[])
    session_id: str | UUID | None = Field(default="")
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )
    flow_id: str | UUID | None = None
    error: bool = Field(default=False)
    edit: bool = Field(default=False)
    properties: Properties = Field(default_factory=Properties)
    category: Literal["message", "error", "warning", "info"] | None = "message"
    duration: int | None = None

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if isinstance(value, UUID):
            value = str(value)
        return value

    @field_validator("properties", mode="before")
    @classmethod
    def validate_properties(cls, value):
        if isinstance(value, str):
            value = Properties.model_validate_json(value)
        elif isinstance(value, dict):
            value = Properties.model_validate(value)
        return value

    @field_serializer("flow_id")
    def serialize_flow_id(self, value):
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        try:
            # Try parsing with timezone
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                # Try parsing without timezone
                dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                # If parsing fails, return current timestamp
                return datetime.now(timezone.utc)

    def set_flow_id(self, flow_id: str) -> None:
        """Set the flow ID for this message."""
        self.flow_id = flow_id

    @classmethod
    def from_lc_message(cls, lc_message: BaseMessage) -> Message:
        """Create a Message from a LangChain message.

        This is a simplified version that creates basic Message objects.
        """
        sender = MESSAGE_SENDER_AI if isinstance(lc_message, AIMessage) else MESSAGE_SENDER_USER
        sender_name = MESSAGE_SENDER_NAME_AI if isinstance(lc_message, AIMessage) else MESSAGE_SENDER_NAME_USER

        return cls(
            text=lc_message.content,
            sender=sender,
            sender_name=sender_name,
        )

    def to_lc_message(self) -> BaseMessage:
        """Convert to LangChain message.

        This is a simplified version that creates basic LangChain messages.
        """
        content = str(self.text) if self.text else ""

        if self.sender == MESSAGE_SENDER_AI:
            return AIMessage(content=content)
        if self.sender == "System":
            return SystemMessage(content=content)
        return HumanMessage(content=content)

    @classmethod
    def from_template(cls, template: str, **variables) -> Message:
        """Create a Message from a template string with variables.

        This is a simplified version for the base class.
        """
        try:
            formatted_text = template.format(**variables)
        except KeyError:
            # If template variables are missing, use the template as-is
            formatted_text = template

        return cls(text=formatted_text)

    def format_text(self) -> str:
        """Format the message text.

        This is a simplified version that just returns the text as string.
        """
        if isinstance(self.text, str):
            return self.text
        return str(self.text) if self.text else ""
