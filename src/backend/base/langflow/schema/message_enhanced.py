from __future__ import annotations

import json
import traceback
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from langchain_core.prompts.chat import BaseChatPromptTemplate, ChatPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate
from lfx.schema.message import Message as LfxMessage
from loguru import logger
from pydantic import ConfigDict, Field, field_serializer, field_validator

from langflow.base.prompts.utils import dict_values_to_string
from langflow.schema.content_block import ContentBlock
from langflow.schema.data import Data
from langflow.schema.image import Image, get_file_paths, is_image_file
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
        file_content_dicts = []
        for file_ in self.files or []:
            if isinstance(file_, str):
                file_content_dict = {"file_name": file_, "type": "file", "file_path": file_}
            elif isinstance(file_, Image):
                file_content_dict = create_image_content_dict(file_)
            else:
                file_content_dict = {"type": "unknown"}
            file_content_dicts.append(file_content_dict)
        return file_content_dicts

    def get_file_paths(self):
        """Get file paths from files."""
        return get_file_paths(self.files or [])

    def load_lc_prompt(self):
        """Load a LangChain prompt from the message."""
        # Enhanced prompt loading logic
        template_data = json.loads(self.text)
        template_format = template_data.get("_type")

        if template_format == "prompt":
            return PromptTemplate.from_template(template_data.get("template"))
        if template_format in ["chat", "messages"]:
            return ChatPromptTemplate.from_messages(template_data.get("messages", []))
        return PromptTemplate.from_template(self.text)

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

    @classmethod
    def from_template(cls, template: str, **variables) -> Message:
        """Create a Message from a template string with variables."""
        try:
            # Enhanced template formatting with variable validation
            formatted_text = template.format(**dict_values_to_string(variables))
        except KeyError as e:
            logger.warning(f"Template variable {e} not found in variables: {list(variables.keys())}")
            formatted_text = template
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error formatting template: {e}")
            formatted_text = template

        return cls(text=formatted_text)

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
