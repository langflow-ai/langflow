from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ConfigDict, Field, field_serializer, field_validator

from lfx.schema.data import Data
from lfx.schema.properties import Properties
from lfx.utils.schemas import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


def timestamp_to_datetime_validator(value: Any) -> datetime:
    """Convert timestamp to datetime object for base Message class."""
    if isinstance(value, datetime):
        # Ensure timezone is UTC
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        # Parse string timestamp
        try:
            if " UTC" in value or " utc" in value.upper():
                cleaned_value = value.replace(" UTC", "").replace(" utc", "")
                dt = datetime.strptime(cleaned_value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                return dt.replace(tzinfo=timezone.utc)
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    # For other types, return current time
    return datetime.now(timezone.utc)


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
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
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

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, value):
        """Convert timestamp to string format for storage."""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S UTC")
        if isinstance(value, str):
            # Validate the string format and standardize it
            try:
                # Handle format with timezone
                if " UTC" in value.upper():
                    return value
                time_date_parts = 2
                if " " in value and len(value.split()) == time_date_parts:
                    # Format: "YYYY-MM-DD HH:MM:SS"
                    return f"{value} UTC"
                # Try to parse and reformat
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                # If parsing fails, return current time as string
                return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            # For other types, return current time as string
            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @field_serializer("flow_id")
    def serialize_flow_id(self, value):
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        """Keep timestamp as datetime object for model_dump()."""
        if isinstance(value, datetime):
            # Ensure timezone is UTC
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            # Parse string back to datetime
            try:
                # Handle format with timezone
                if " UTC" in value or " utc" in value.upper():
                    cleaned_value = value.replace(" UTC", "").replace(" utc", "")
                    dt = datetime.strptime(cleaned_value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                    return dt.replace(tzinfo=timezone.utc)
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)
        # For other types, return current time
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

    @classmethod
    async def create(cls, **kwargs):
        """If files are present, create the message in a separate thread as is_image_file is blocking."""
        if "files" in kwargs:
            return await asyncio.to_thread(cls, **kwargs)
        return cls(**kwargs)

    def format_text(self) -> str:
        """Format the message text.

        This is a simplified version that just returns the text as string.
        """
        if isinstance(self.text, str):
            return self.text
        return str(self.text) if self.text else ""
