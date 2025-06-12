from __future__ import annotations

import asyncio
import json
import re
import traceback
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from langchain_core.load import load
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import BaseChatPromptTemplate, ChatPromptTemplate, PromptTemplate
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator

from langflow.base.prompts.utils import dict_values_to_string
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import ErrorContent
from langflow.schema.data import Data
from langflow.schema.image import Image, get_file_paths, is_image_file
from langflow.schema.properties import Properties, Source
from langflow.schema.validators import timestamp_to_str, timestamp_to_str_validator
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)
from langflow.utils.image import create_data_url

if TYPE_CHECKING:
    from langflow.schema.dataframe import DataFrame


class Message(Data):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # Helper class to deal with image data
    text_key: str = "text"
    text: str | AsyncIterator | Iterator | None = Field(default="")
    sender: str | None = None
    sender_name: str | None = None
    files: list[str | Image] | None = Field(default=[])
    session_id: str | UUID | None = Field(default="")
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )
    flow_id: str | UUID | None = None
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

    properties: Properties = Field(default_factory=Properties)
    category: Literal["message", "error", "warning", "info"] | None = "message"
    content_blocks: list[ContentBlock] = Field(default_factory=list)
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
        # value may start with [ or not
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
            # Try parsing without timezone
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        if not value:
            value = []
        elif not isinstance(value, list):
            value = [value]
        return value

    def model_post_init(self, /, _context: Any) -> None:
        new_files: list[Any] = []
        for file in self.files or []:
            if is_image_file(file):
                new_files.append(Image(path=file))
            else:
                new_files.append(file)
        self.files = new_files
        if "timestamp" not in self.data:
            self.data["timestamp"] = self.timestamp

    def set_flow_id(self, flow_id: str) -> None:
        self.flow_id = flow_id

    def to_lc_message(
        self,
    ) -> BaseMessage:
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
    def from_lc_message(cls, lc_message: BaseMessage) -> Message:
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

    @classmethod
    def from_data(cls, data: Data) -> Message:
        """Converts Data to a Message.

        Args:
            data: The Data to convert.

        Returns:
            The converted Message.
        """
        return cls(
            text=data.text,
            sender=data.sender,
            sender_name=data.sender_name,
            files=data.files,
            session_id=data.session_id,
            timestamp=data.timestamp,
            flow_id=data.flow_id,
            error=data.error,
            edit=data.edit,
        )

    @field_serializer("text", mode="plain")
    def serialize_text(self, value):
        if isinstance(value, AsyncIterator | Iterator):
            return ""
        return value

    # Keep this async method for backwards compatibility
    def get_file_content_dicts(self):
        content_dicts = []
        files = get_file_paths(self.files)

        for file in files:
            if isinstance(file, Image):
                content_dicts.append(file.to_content_dict())
            else:
                image_url = create_data_url(file)
                content_dicts.append({"type": "image_url", "image_url": {"url": image_url}})
        return content_dicts

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

    @classmethod
    def from_lc_prompt(
        cls,
        prompt: BaseChatPromptTemplate,
    ):
        prompt_json = prompt.to_json()
        return cls(prompt=prompt_json)

    def format_text(self):
        prompt_template = PromptTemplate.from_template(self.template)
        variables_with_str_values = dict_values_to_string(self.variables)
        formatted_prompt = prompt_template.format(**variables_with_str_values)
        self.text = formatted_prompt
        return formatted_prompt

    @classmethod
    async def from_template_and_variables(cls, template: str, **variables):
        # This method has to be async for backwards compatibility with versions
        # >1.0.15, <1.1
        return cls.from_template(template, **variables)

    # Define a sync version for backwards compatibility with versions >1.0.15, <1.1
    @classmethod
    def from_template(cls, template: str, **variables):
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

        instance.prompt = jsonable_encoder(prompt_template.to_json())
        instance.messages = instance.prompt.get("kwargs", {}).get("messages", [])
        return instance

    @classmethod
    async def create(cls, **kwargs):
        """If files are present, create the message in a separate thread as is_image_file is blocking."""
        if "files" in kwargs:
            return await asyncio.to_thread(cls, **kwargs)
        return cls(**kwargs)

    def to_data(self) -> Data:
        return Data(data=self.data)

    def to_dataframe(self) -> DataFrame:
        from langflow.schema.dataframe import DataFrame  # Local import to avoid circular import

        return DataFrame(data=[self])


class DefaultModel(BaseModel):
    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def json(self, **kwargs):
        # Usa a função de serialização personalizada
        return super().model_dump_json(**kwargs, encoder=self.custom_encoder)

    @staticmethod
    def custom_encoder(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        msg = f"Object of type {obj.__class__.__name__} is not JSON serializable"
        raise TypeError(msg)


class MessageResponse(DefaultModel):
    id: str | UUID | None = Field(default=None)
    flow_id: UUID | None = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender: str
    sender_name: str
    session_id: str
    text: str
    files: list[str] = []
    edit: bool
    duration: float | None = None

    properties: Properties | None = None
    category: str | None = None
    content_blocks: list[ContentBlock] | None = None

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        if isinstance(v, list):
            return [cls.validate_content_blocks(block) for block in v]
        if isinstance(v, dict):
            return ContentBlock.model_validate(v)
        return v

    @field_validator("properties", mode="before")
    @classmethod
    def validate_properties(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        return v

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        return v

    @field_serializer("timestamp")
    @classmethod
    def serialize_timestamp(cls, v):
        return timestamp_to_str(v)

    @field_serializer("files")
    @classmethod
    def serialize_files(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v

    @classmethod
    def from_message(cls, message: Message, flow_id: str | None = None):
        # first check if the record has all the required fields
        if message.text is None or not message.sender or not message.sender_name:
            msg = "The message does not have the required fields (text, sender, sender_name)."
            raise ValueError(msg)
        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message.text,
            session_id=message.session_id,
            files=message.files or [],
            timestamp=message.timestamp,
            flow_id=flow_id,
        )


class ErrorMessage(Message):
    """A message class specifically for error messages with predefined error-specific attributes."""

    @staticmethod
    def _format_markdown_reason(exception: BaseException) -> str:
        """Format the error reason with markdown formatting."""
        reason = f"**{exception.__class__.__name__}**\n"
        if hasattr(exception, "body") and isinstance(exception.body, dict) and "message" in exception.body:
            reason += f" - **{exception.body.get('message')}**\n"
        elif hasattr(exception, "code"):
            reason += f" - **Code: {exception.code}**\n"
        elif hasattr(exception, "args") and exception.args:
            reason += f" - **Details: {exception.args[0]}**\n"
        elif isinstance(exception, ValidationError):
            reason += f" - **Details:**\n\n```python\n{exception!s}\n```\n"
        else:
            reason += " - **An unknown error occurred.**\n"
        return reason

    @staticmethod
    def _format_plain_reason(exception: BaseException) -> str:
        """Format the error reason without markdown."""
        if hasattr(exception, "body") and isinstance(exception.body, dict) and "message" in exception.body:
            reason = f"{exception.body.get('message')}\n"
        elif hasattr(exception, "_message"):
            reason = f"{exception._message()}\n" if callable(exception._message) else f"{exception._message}\n"
        elif hasattr(exception, "code"):
            reason = f"Code: {exception.code}\n"
        elif hasattr(exception, "args") and exception.args:
            reason = f"{exception.args[0]}\n"
        elif isinstance(exception, ValidationError):
            reason = f"{exception!s}\n"
        elif hasattr(exception, "detail"):
            reason = f"{exception.detail}\n"
        elif hasattr(exception, "message"):
            reason = f"{exception.message}\n"
        else:
            reason = "An unknown error occurred.\n"
        return reason

    def __init__(
        self,
        exception: BaseException,
        session_id: str | None = None,
        source: Source | None = None,
        trace_name: str | None = None,
        flow_id: UUID | str | None = None,
    ) -> None:
        # This is done to avoid circular imports
        if exception.__class__.__name__ == "ExceptionWithMessageError" and exception.__cause__ is not None:
            exception = exception.__cause__

        plain_reason = self._format_plain_reason(exception)
        markdown_reason = self._format_markdown_reason(exception)
        # Get the sender ID
        if trace_name:
            match = re.search(r"\((.*?)\)", trace_name)
            if match:
                match.group(1)

        super().__init__(
            session_id=session_id,
            sender=source.display_name if source else None,
            sender_name=source.display_name if source else None,
            text=plain_reason,
            properties=Properties(
                text_color="red",
                background_color="red",
                edited=False,
                source=source,
                icon="error",
                allow_markdown=False,
                targets=[],
            ),
            category="error",
            error=True,
            content_blocks=[
                ContentBlock(
                    title="Error",
                    contents=[
                        ErrorContent(
                            type="error",
                            component=source.display_name if source else None,
                            field=str(exception.field) if hasattr(exception, "field") else None,
                            reason=markdown_reason,
                            solution=str(exception.solution) if hasattr(exception, "solution") else None,
                            traceback=traceback.format_exc(),
                        )
                    ],
                )
            ],
            flow_id=flow_id,
        )
