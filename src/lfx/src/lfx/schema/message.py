from __future__ import annotations

import asyncio
import json
import traceback
from collections.abc import AsyncIterator, Iterator  # noqa: TC003
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from langchain_core.load import load
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ConfigDict, Field, field_serializer, field_validator

from lfx.base.prompts.utils import dict_values_to_string
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.image import Image
from lfx.schema.properties import Properties
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER

if TYPE_CHECKING:
    from langchain_core.prompts import BaseChatPromptTemplate

    from lfx.schema.dataframe import DataFrame


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
    id: str | UUID | None = None
    text_key: str = "text"
    text: str | AsyncIterator | Iterator | None = Field(default="")
    sender: str | None = None
    sender_name: str | None = None
    files: list[str | Image] | None = Field(default=[])
    content_blocks: list[ContentBlock] = Field(default_factory=list)
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

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, value):
        """Convert content_blocks from dicts to ContentBlock objects."""
        if isinstance(value, list):
            return [
                ContentBlock.model_validate_json(v) if isinstance(v, str) else ContentBlock.model_validate(v)
                for v in value
            ]
        if isinstance(value, str):
            value = json.loads(value) if value.startswith("[") else [ContentBlock.model_validate_json(value)]
        return value

    @field_validator("properties", mode="before")
    @classmethod
    def validate_properties(cls, value):
        if isinstance(value, str):
            value = Properties.model_validate_json(value)
        elif isinstance(value, dict):
            value = Properties.model_validate(value)
        elif isinstance(value, Properties):
            return value
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

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        if not value:
            value = []
        elif not isinstance(value, list):
            value = [value]
        return value

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

    def load_lc_prompt(self):
        if "prompt" not in self:
            msg = "Prompt is required."
            raise ValueError(msg)
        # self.prompt was passed through jsonable_encoder
        # so inner messages are not BaseMessage
        # we need to convert them to BaseMessage
        messages = []
        for message in self.prompt.get("kwargs", {}).get("messages", []):
            match message:
                case HumanMessage():
                    messages.append(message)
                case _ if message.get("type") == "human":
                    messages.append(HumanMessage(content=message.get("content")))
                case _ if message.get("type") == "system":
                    messages.append(SystemMessage(content=message.get("content")))
                case _ if message.get("type") == "ai":
                    messages.append(AIMessage(content=message.get("content")))

        self.prompt["kwargs"]["messages"] = messages
        return load(self.prompt)

    def get_file_content_dicts(self):
        """Get file content dictionaries for all files in the message."""
        from lfx.schema.image import get_file_paths
        from lfx.utils.image import create_image_content_dict

        content_dicts = []
        files = get_file_paths(self.files)

        for file in files:
            if isinstance(file, Image):
                content_dicts.append(file.to_content_dict())
            else:
                content_dicts.append(create_image_content_dict(file))
        return content_dicts

    def to_lc_message(self) -> BaseMessage:
        """Converts the Data to a BaseMessage.

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        # The idea of this function is to be a helper to convert a Data to a BaseMessage
        # It will use the "sender" key to determine if the message is Human or AI
        # If the key is not present, it will default to AI
        # But first we check if all required keys are present in the data dictionary
        # they are: "text", "sender"
        if self.text is None or not self.sender:
            from loguru import logger

            logger.warning("Missing required keys ('text', 'sender') in Message, defaulting to HumanMessage.")
        text = "" if not isinstance(self.text, str) else self.text

        if self.sender == MESSAGE_SENDER_USER or not self.sender:
            if self.files:
                contents = [{"type": "text", "text": text}]
                contents.extend(self.get_file_content_dicts())
                human_message = HumanMessage(content=contents)
            else:
                human_message = HumanMessage(content=text)
            return human_message

        return AIMessage(content=text)

    @classmethod
    def from_lc_prompt(cls, prompt: BaseChatPromptTemplate) -> Message:
        """Create a Message from a LangChain prompt template."""
        prompt_json = prompt.to_json()
        return cls(prompt=prompt_json)

    @classmethod
    def from_template(cls, template: str, **variables) -> Message:
        """Create a Message from a template string with variables.

        This matches the message_original implementation exactly.
        """
        from fastapi.encoders import jsonable_encoder
        from langchain_core.prompts.chat import ChatPromptTemplate

        instance = cls(template=template, variables=variables)
        text = instance.format_text()
        message = HumanMessage(content=text)
        contents = []
        for value in variables.values():
            if isinstance(value, cls) and value.files:
                content_dicts = value.get_file_content_dicts()
                contents.extend(content_dicts)
        if contents:
            message = HumanMessage(content=[{"type": "text", "text": text}, *contents])

        prompt_template = ChatPromptTemplate.from_messages([message])

        instance.data["prompt"] = jsonable_encoder(prompt_template.to_json())
        instance.data["messages"] = instance.data["prompt"].get("kwargs", {}).get("messages", [])
        return instance

    @classmethod
    async def from_template_and_variables(cls, template: str, **variables) -> Message:
        """Backwards compatibility method for versions >1.0.15, <1.1."""
        return cls.from_template(template, **variables)

    @classmethod
    async def create(cls, **kwargs):
        """If files are present, create the message in a separate thread as is_image_file is blocking."""
        if "files" in kwargs:
            return await asyncio.to_thread(cls, **kwargs)
        return cls(**kwargs)

    def to_data(self) -> Data:
        return Data(data=self.data)

    def to_dataframe(self) -> DataFrame:
        from lfx.schema.dataframe import DataFrame  # Local import to avoid circular import

        return DataFrame(data=[self])

    def get_text(self) -> str:
        """Get the message text as a string.

        Returns:
            str: The text content of the message.
        """
        if isinstance(self.text, str):
            return self.text
        return str(self.text) if self.text else ""

    def format_text(self) -> str:
        """Format the message text using template and variables.

        This matches the message_original implementation.
        """
        # Check if we have template and variables in data
        if "template" in self.data and "variables" in self.data:
            from langchain_core.prompts.prompt import PromptTemplate

            prompt_template = PromptTemplate.from_template(self.data["template"])
            variables_with_str_values = dict_values_to_string(self.data["variables"])
            formatted_prompt = prompt_template.format(**variables_with_str_values)
            self.text = formatted_prompt
            return formatted_prompt

        # Fallback to simple text formatting
        if isinstance(self.text, str):
            return self.text
        return str(self.text) if self.text else ""


class ErrorMessage(Message):
    """Error message with traceback formatting."""

    def __init__(
        self,
        *,
        text: str = "",
        exception: BaseException | None = None,
        traceback_str: str = "",
        **data,
    ):
        if exception:
            text = self._format_markdown_reason(exception)
        elif traceback_str:
            text = traceback_str

        super().__init__(
            text=text,
            category="error",
            error=True,
            **data,
        )

    @staticmethod
    def _format_markdown_reason(exception: BaseException) -> str:
        """Format exception as markdown."""
        exception_type = type(exception).__name__
        exception_message = str(exception)
        traceback_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        return f"""## {exception_type}

{exception_message}

### Traceback
```python
{traceback_str}
```
"""

    @staticmethod
    def _format_plain_reason(exception: BaseException) -> str:
        """Format exception as plain text."""
        exception_type = type(exception).__name__
        exception_message = str(exception)
        traceback_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        return f"{exception_type}: {exception_message}\n\nTraceback:\n{traceback_str}"


Message.model_rebuild()

__all__ = ["ContentBlock", "ErrorMessage", "Message"]
