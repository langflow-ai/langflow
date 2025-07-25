from __future__ import annotations

import json
import traceback
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from langchain_core.load import load
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts.chat import BaseChatPromptTemplate, ChatPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate
from lfx.schema.image import Image, get_file_paths, is_image_file
from lfx.schema.message import Message as LfxMessage
from lfx.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)
from loguru import logger
from pydantic import ConfigDict, Field, field_serializer, field_validator

from langflow.schema.content_block import ContentBlock
from langflow.schema.data import Data
from langflow.utils.image import create_image_content_dict

if TYPE_CHECKING:
    from langflow.schema.dataframe import DataFrame


class Message(LfxMessage):
    """Enhanced Message class with full langflow functionality.

    This inherits from the base lfx.schema.message.Message and adds
    complex functionality that depends on langflow-specific modules.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Override files to support Image objects
    files: list[str | Image] | None = Field(default=[])
    content_blocks: list[ContentBlock] = Field(default_factory=list)

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, value):
        # value may start with [ or not
        if isinstance(value, list):
            return [
                ContentBlock.model_validate_json(v) if isinstance(v, str) else ContentBlock.model_validate(v)
                for v in value
            ]
        if isinstance(value, str):
            value = json.loads(value) if value.startswith("[") else [ContentBlock.model_validate_json(value)]
        return value

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        if not value:
            return []
        new_files = []
        for file_ in value:
            if isinstance(file_, str):
                # Check if it's a valid image file
                if is_image_file(file_):
                    new_files.append(Image(path=file_))
                else:
                    new_files.append(file_)
            elif isinstance(file_, Image):
                new_files.append(file_)
            elif isinstance(file_, dict) and "path" in file_:
                new_files.append(Image.model_validate(file_))
        return new_files

    @field_validator("properties", mode="before")
    @classmethod
    def validate_properties(cls, value):
        """Enhanced properties validator that handles both langflow and lfx Properties classes."""
        from lfx.schema.properties import Properties as LfxProperties

        from langflow.schema.properties import Properties as LangflowProperties

        if isinstance(value, str):
            return LfxProperties.model_validate_json(value)
        if isinstance(value, dict):
            return LfxProperties.model_validate(value)
        if isinstance(value, LfxProperties):
            return value
        if isinstance(value, LangflowProperties):
            # Convert langflow Properties to lfx Properties for compatibility
            return LfxProperties.model_validate(value.model_dump())
        if hasattr(value, "model_dump"):
            # Generic case for any pydantic model with the right structure
            return LfxProperties.model_validate(value.model_dump())
        return value

    def model_post_init(self, /, _context: Any) -> None:
        if self.files:
            self.files = self.get_file_paths()

    @field_serializer("text")
    def serialize_text(self, value):
        if isinstance(value, AsyncIterator | Iterator):
            return "Unconsumed Stream"
        return value

    def get_file_content_dicts(self):
        """Get file content as dictionaries."""
        content_dicts = []
        files = self.get_file_paths()

        for file in files:
            if isinstance(file, Image):
                content_dicts.append(file.to_content_dict())
            else:
                content_dicts.append(create_image_content_dict(file))
        return content_dicts

    def get_file_paths(self):
        """Get file paths from files."""
        return get_file_paths(self.files or [])

    def load_lc_prompt(self):
        """Load a LangChain prompt from the message."""
        if self.prompt:
            # Original behavior: reconstruct from stored prompt
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
            prompt_template = load(self.prompt)

            # The test expects the prompt to have formatted messages, not template messages
            # So we need to format it and create a new ChatPromptTemplate with actual messages
            if hasattr(prompt_template, "format_messages"):
                # If it's a ChatPromptTemplate, format the messages
                formatted_messages = prompt_template.format_messages()
                return ChatPromptTemplate.from_messages(formatted_messages)
            return prompt_template

        # Try to parse self.text as JSON (new enhanced implementation)
        try:
            template_data = json.loads(str(self.text))
            template_format = template_data.get("_type")

            if template_format == "prompt":
                return PromptTemplate.from_template(template_data.get("template"))
            if template_format in ["chat", "messages"]:
                return ChatPromptTemplate.from_messages(template_data.get("messages", []))
        except (json.JSONDecodeError, TypeError):
            # If parsing fails, treat self.text as a simple template
            pass

        # Fallback: treat self.text as a simple template
        return ChatPromptTemplate.from_template(str(self.text) if self.text else "")

    @classmethod
    def from_lc_prompt(
        cls,
        lc_prompt: BaseChatPromptTemplate | PromptTemplate,
        variables: dict | None = None,
    ) -> Message:
        """Create a Message from a LangChain prompt."""
        if isinstance(lc_prompt, BaseChatPromptTemplate):
            messages = lc_prompt.format_messages(**(variables or {}))
            # Convert to a single text message
            text = "\n".join([msg.content for msg in messages])
        elif isinstance(lc_prompt, PromptTemplate):
            text = lc_prompt.format(**(variables or {}))
        else:
            text = str(lc_prompt)

        return cls(text=text)

    @classmethod
    def from_lc_message(cls, lc_message: BaseMessage) -> Message:
        """Create a Message from a LangChain message.

        Args:
            lc_message: The LangChain message to convert.

        Returns:
            Message: The converted Message.
        """
        if lc_message.type == "human":
            sender = MESSAGE_SENDER_USER
            sender_name = MESSAGE_SENDER_NAME_USER
        elif lc_message.type == "ai":
            sender = MESSAGE_SENDER_AI
            sender_name = MESSAGE_SENDER_NAME_AI
        elif lc_message.type == "system":
            sender = "System"
            sender_name = "System"
        else:
            sender = lc_message.type
            sender_name = lc_message.type

        return cls(text=lc_message.content, sender=sender, sender_name=sender_name)

    def format_text(self):
        """Format the message text with enhanced formatting."""
        if isinstance(self.text, AsyncIterator | Iterator):
            return "Unconsumed Stream"

        text = str(self.text) if self.text else ""

        # Enhanced formatting with content blocks
        if self.content_blocks:
            formatted_blocks = []
            for block in self.content_blocks:
                if hasattr(block, "format"):
                    formatted_blocks.append(block.format())
                else:
                    formatted_blocks.append(str(block))
            if formatted_blocks:
                text += "\n\n" + "\n".join(formatted_blocks)

        return text

    def to_lc_message(self) -> BaseMessage:
        """Convert to LangChain message with enhanced file handling."""
        if self.text is None or not self.sender:
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
    def from_template(cls, template: str, **variables) -> Message:
        """Create a Message from a template string with variables.

        This enhanced version stores the prompt information for reconstruction.
        """
        instance = cls(template=template, variables=variables)
        text = template
        try:
            formatted_text = template.format(**variables)
            text = formatted_text
        except KeyError:
            # If template variables are missing, use the template as-is
            pass

        instance.text = text
        message = HumanMessage(content=text)
        contents = []

        # Handle file content if any variables contain Message objects with files
        for value in variables.values():
            if isinstance(value, cls) and value.files:
                content_dicts = value.get_file_content_dicts()
                contents.extend(content_dicts)

        if contents:
            message = HumanMessage(content=[{"type": "text", "text": text}, *contents])

        prompt_template = ChatPromptTemplate.from_messages([message])
        instance.prompt = jsonable_encoder(prompt_template.to_json())
        instance.messages = instance.prompt.get("kwargs", {}).get("messages", [])
        return instance

    @classmethod
    def from_data(cls, data: Data) -> Message:
        """Create a Message from Data object."""
        return cls(
            text=str(data.get_text()) if hasattr(data, "get_text") else str(data),
            data=data.data if hasattr(data, "data") else None,
        )

    def to_data(self) -> Data:
        """Convert message to Data object."""
        return Data(data={"text": self.format_text()})

    def to_dataframe(self) -> DataFrame:
        """Convert message to DataFrame."""
        from langflow.schema.dataframe import DataFrame  # Local import to avoid circular import

        return DataFrame.from_records([{"text": self.format_text(), "sender": self.sender}])

    def json(self, **kwargs):
        """Enhanced JSON serialization."""

        # Custom encoder for complex types
        def custom_encoder(obj):
            if isinstance(obj, AsyncIterator | Iterator):
                return "Unconsumed Stream"
            if isinstance(obj, BaseException):
                return str(obj)
            return jsonable_encoder(obj)

        data = self.model_dump(**kwargs)
        return json.dumps(data, default=custom_encoder)

    @classmethod
    def from_message(cls, message: Message, flow_id: str | None = None):
        """Create a Message from another Message."""
        new_message = cls.model_validate(message.model_dump())
        if flow_id:
            new_message.set_flow_id(flow_id)
        return new_message


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
