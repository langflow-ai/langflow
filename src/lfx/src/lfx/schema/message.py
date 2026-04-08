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
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

if TYPE_CHECKING:
    from langchain_core.prompts.chat import BaseChatPromptTemplate

from pydantic import TypeAdapter

from lfx.base.prompts.utils import dict_values_to_string
from lfx.log.logger import logger
from lfx.schema.content_block import ContentBlock, ContentType
from lfx.schema.content_types import ErrorContent, TextContent
from lfx.schema.data import Data
from lfx.schema.image import Image, get_file_paths, is_image_file
from lfx.schema.properties import Properties, Source
from lfx.schema.validators import timestamp_to_str, timestamp_to_str_validator
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER
from lfx.utils.image import create_image_content_dict
from lfx.utils.mustache_security import safe_mustache_render

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame

_CONTENT_TYPE_ADAPTER = TypeAdapter(ContentType)


class Message(Data):
    """Message schema for Langflow.

    Message ID Semantics:
    - Messages only have an ID after being stored in the database
    - Messages that are skipped (via Component._should_skip_message) will NOT have an ID
    - Always use get_id(), has_id(), or require_id() methods to safely access the ID
    - Never access message.id directly without checking if it exists first

    Safe ID Access Patterns:
    - Use get_id() when ID may or may not exist (returns None if missing)
    - Use has_id() to check if ID exists before operations that require it
    - Use require_id() when ID is required (raises ValueError if missing)

    Example:
        message_id = message.get_id()  # Safe: returns None if no ID
        if message.has_id():
            # Safe to use message_id
            do_something_with_id(message_id)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    # Helper class to deal with image data
    text_key: str = "text"
    sender: str | None = None
    sender_name: str | None = None
    files: list[str | Image] | None = Field(default=[])
    session_id: str | UUID | None = Field(default="")
    context_id: str | UUID | None = Field(default="")
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )
    flow_id: str | UUID | None = None
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

    properties: Properties = Field(default_factory=Properties)
    category: Literal["message", "error", "warning", "info"] | None = "message"
    content_blocks: list[ContentType | ContentBlock] = Field(default_factory=list)
    duration: int | None = None
    session_metadata: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def _fold_text_into_content_blocks(cls, data):
        if not isinstance(data, dict):
            return data
        text = data.get("text")
        if text and not isinstance(text, str):
            # AsyncIterator/Iterator for streaming -- leave in data for model_post_init
            return data
        # Don't auto-wrap text into content_blocks. Text-only messages keep
        # content_blocks empty for backwards compatibility with the frontend.
        # content_blocks is populated explicitly by components that produce
        # rich content (agents, multimodal, etc.).
        return data

    @computed_field
    @property
    def text(self) -> str:
        """Extract text from content_blocks, or fall back to data dict.

        Always returns a string. For streaming access, use `text_stream` property.
        """
        # If content_blocks has TextContent, derive from there
        text_from_blocks = "".join(b.text for b in self.content_blocks if isinstance(b, TextContent))
        if text_from_blocks:
            return text_from_blocks
        # Fall back to data dict (text-only messages, backwards compat)
        return self.data.get(self.text_key, "") or ""

    @text.setter
    def text(self, value: str | AsyncIterator | Iterator | None) -> None:
        """Replace text content or set a stream for later consumption."""
        if isinstance(value, AsyncIterator | Iterator):
            object.__setattr__(self, "_text_stream", value)
            return
        # Clear any pending/exhausted stream
        self.__dict__.pop("_text_stream", None)
        # If content_blocks has non-text items, update TextContent in content_blocks
        non_text = [b for b in self.content_blocks if not isinstance(b, TextContent)]
        if non_text:
            # Rich message -- update content_blocks
            if value:
                object.__setattr__(self, "content_blocks", [TextContent(text=str(value)), *non_text])
            else:
                object.__setattr__(self, "content_blocks", non_text)
        else:
            # Text-only message -- clear content_blocks, store in data dict
            object.__setattr__(self, "content_blocks", [])
        # Keep self.data["text"] in sync for backwards compatibility
        self.data[self.text_key] = value or ""

    @property
    def text_stream(self) -> AsyncIterator | Iterator | None:
        """Access the pending text stream, if any. Used by streaming infrastructure."""
        return self.__dict__.get("_text_stream")

    def get_text(self):
        """Return text derived from content_blocks (overrides Data.get_text)."""
        return self.text

    @model_serializer(mode="plain", when_used="json")
    def serialize_model(self):
        """Override Data.serialize_model to filter out non-serializable stream objects."""
        return {
            k: v.to_json() if hasattr(v, "to_json") else v
            for k, v in self.data.items()
            if not isinstance(v, AsyncIterator | Iterator)
        }

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if isinstance(value, UUID):
            value = str(value)
        return value

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, value):
        def _parse_item(item):
            # Already a Pydantic model instance -- keep as-is
            if isinstance(item, BaseModel):
                return item
            # JSON string -- parse it
            if isinstance(item, str):
                parsed = json.loads(item)
                return _parse_item(parsed)
            # Dict -- determine if it's a flat ContentType or grouped ContentBlock
            if isinstance(item, dict):
                # If it has "title" and "contents", it's a ContentBlock (grouped)
                if "title" in item and "contents" in item:
                    return ContentBlock.model_validate(item)
                # Otherwise it's a flat ContentType (TextContent, ToolContent, etc.)
                if "type" in item:
                    return _CONTENT_TYPE_ADAPTER.validate_python(item)
                # Fallback to ContentBlock
                return ContentBlock.model_validate(item)
            return item

        if isinstance(value, str):
            value = json.loads(value) if value.startswith("[") else [value]
        if isinstance(value, list):
            return [_parse_item(v) for v in value]
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
        # If text in data dict is an iterator/stream, move it to __dict__ for direct access
        text_val = self.data.get("text")
        if text_val is not None and not isinstance(text_val, str):
            self.data.pop("text", None)
            self.__dict__["_text_stream"] = text_val
        new_files: list[Any] = []
        for file in self.files or []:
            # Skip if already an Image instance
            if isinstance(file, Image):
                new_files.append(file)
            # Get the path string if file is a dict or has path attribute
            elif isinstance(file, dict) and "path" in file:
                file_path = file["path"]
                if file_path and is_image_file(file_path):
                    new_files.append(Image(path=file_path))
                else:
                    new_files.append(file_path if file_path else file)
            elif hasattr(file, "path") and file.path:
                if is_image_file(file.path):
                    new_files.append(Image(path=file.path))
                else:
                    new_files.append(file.path)
            elif isinstance(file, str) and is_image_file(file):
                new_files.append(Image(path=file))
            else:
                new_files.append(file)
        self.files = new_files
        if "timestamp" not in self.data:
            self.data["timestamp"] = self.timestamp
        # Sync self.data["text"] from content_blocks for backwards compatibility
        text_val = self.text
        self.data[self.text_key] = text_val if isinstance(text_val, str) else ""

    def set_flow_id(self, flow_id: str) -> None:
        self.flow_id = flow_id

    def to_lc_message(
        self,
        model_name: str | None = None,
    ) -> BaseMessage:
        """Converts the Message to a BaseMessage.

        Args:
            model_name: The model name to use for conversion. Optional.

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        text = self.text  # reads from content_blocks via computed property
        if not isinstance(text, str):
            text = ""
        if not text or not self.sender:
            logger.warning("Missing required keys ('text', 'sender') in Message, defaulting to HumanMessage.")

        if self.sender == MESSAGE_SENDER_USER or not self.sender:
            if self.files:
                contents = [{"type": "text", "text": text}]
                file_contents = self.get_file_content_dicts(model_name)
                contents.extend(file_contents)
                return HumanMessage(content=contents)
            return HumanMessage(content=text)

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
        elif lc_message.type == "tool":
            sender = "Tool"
            sender_name = "Tool"
        else:
            sender = lc_message.type
            sender_name = lc_message.type

        content = lc_message.content
        if isinstance(content, str):
            # Simple text -- use text= parameter, not content_blocks
            return cls(text=content, sender=sender, sender_name=sender_name)
        from lfx.schema.content_types import ImageContent

        blocks = []
        for item in content:
            if isinstance(item, str):
                blocks.append(TextContent(text=item))
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    blocks.append(TextContent(text=item.get("text", "")))
                elif item_type == "image_url":
                    url = item.get("image_url", {}).get("url", "")
                    blocks.append(ImageContent(urls=[url]))
                elif item_type == "image":
                    url = item.get("url") or item.get("source", {}).get("url", "")
                    b64 = item.get("source", {}).get("data") or item.get("base64")
                    mime = item.get("source", {}).get("media_type") or item.get("mime_type")
                    if b64 and mime:
                        blocks.append(ImageContent(base64=b64, mime_type=mime))
                    elif url:
                        blocks.append(ImageContent(urls=[url]))
                else:
                    logger.debug(f"from_lc_message: skipping unsupported content type '{item_type}'")

        # Capture tool calls from AIMessage
        if hasattr(lc_message, "tool_calls") and lc_message.tool_calls:
            from lfx.schema.content_types import ToolContent

            blocks.extend(
                ToolContent(name=tc.get("name", ""), tool_input=tc.get("args", {})) for tc in lc_message.tool_calls
            )

        # Capture usage metadata from AIMessage
        if hasattr(lc_message, "usage_metadata") and lc_message.usage_metadata:
            from lfx.schema.content_types import UsageContent

            um = lc_message.usage_metadata
            blocks.append(
                UsageContent(
                    input_tokens=um.get("input_tokens"),
                    output_tokens=um.get("output_tokens"),
                    model=lc_message.response_metadata.get("model_name")
                    if hasattr(lc_message, "response_metadata")
                    else None,
                )
            )

        return cls(content_blocks=blocks, sender=sender, sender_name=sender_name)

    @classmethod
    def from_data(cls, data: Data) -> Message:
        """Converts Data to a Message.

        Args:
            data: The Data to convert.

        Returns:
            The converted Message.
        """
        kwargs: dict[str, Any] = {"text": data.get_text()}
        # Safely extract optional fields that may not exist on a plain Data object
        for field in (
            "sender",
            "sender_name",
            "files",
            "session_id",
            "context_id",
            "timestamp",
            "flow_id",
            "error",
            "edit",
        ):
            try:
                value = getattr(data, field)
                kwargs[field] = value
            except AttributeError:
                pass
        return cls(**kwargs)

    # Keep this async method for backwards compatibility
    def get_file_content_dicts(self, model_name: str | None = None):
        content_dicts = []
        try:
            files = get_file_paths(self.files)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting file paths: {e}")
            return content_dicts

        for file in files:
            if isinstance(file, Image):
                # Pass the message's flow_id to the Image for proper path resolution
                content_dicts.append(file.to_content_dict(flow_id=self.flow_id))
            else:
                content_dicts.append(create_image_content_dict(file, None, model_name))
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
                case _ if message.get("type") == "tool":
                    messages.append(ToolMessage(content=message.get("content")))

        self.prompt["kwargs"]["messages"] = messages
        return load(self.prompt)

    @classmethod
    def from_lc_prompt(
        cls,
        prompt: BaseChatPromptTemplate,
    ):
        prompt_json = prompt.to_json()
        return cls(prompt=prompt_json)

    def format_text(self, template_format="f-string"):
        if template_format == "mustache":
            # Use our secure mustache renderer
            variables_with_str_values = dict_values_to_string(self.variables)
            formatted_prompt = safe_mustache_render(self.template, variables_with_str_values)
            self.text = formatted_prompt
            return formatted_prompt
        # Use langchain's template for other formats
        from langchain_core.prompts.prompt import PromptTemplate

        prompt_template = PromptTemplate.from_template(self.template, template_format=template_format)
        variables_with_str_values = dict_values_to_string(self.variables)
        formatted_prompt = prompt_template.format(**variables_with_str_values)
        self.text = formatted_prompt
        return formatted_prompt

    @classmethod
    async def from_template_and_variables(cls, template: str, template_format: str = "f-string", **variables):
        # This method has to be async for backwards compatibility with versions
        # >1.0.15, <1.1
        return cls.from_template(template, template_format=template_format, **variables)

    # Define a sync version for backwards compatibility with versions >1.0.15, <1.1
    @classmethod
    def from_template(cls, template: str, template_format: str = "f-string", **variables):
        from langchain_core.prompts.chat import ChatPromptTemplate

        instance = cls(template=template, variables=variables)
        text = instance.format_text(template_format=template_format)
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
        if kwargs.get("files"):
            return await asyncio.to_thread(cls, **kwargs)
        return cls(**kwargs)

    def to_data(self) -> Data:
        return Data(data=self.data)

    def to_dataframe(self) -> DataFrame:
        from lfx.schema.dataframe import DataFrame  # Local import to avoid circular import

        return DataFrame(data=[self])

    def get_id(self) -> str | UUID | None:
        """Safely get the message ID.

        Returns:
            The message ID if it exists, None otherwise.

        Note:
            A message only has an ID if it has been stored in the database.
            Messages that are skipped (via _should_skip_message) will not have an ID.
        """
        return getattr(self, "id", None)

    def has_id(self) -> bool:
        """Check if the message has an ID.

        Returns:
            True if the message has an ID, False otherwise.

        Note:
            A message only has an ID if it has been stored in the database.
            Messages that are skipped (via _should_skip_message) will not have an ID.
        """
        message_id = getattr(self, "id", None)
        return message_id is not None

    def require_id(self) -> str | UUID:
        """Get the message ID, raising an error if it doesn't exist.

        Returns:
            The message ID.

        Raises:
            ValueError: If the message does not have an ID.

        Note:
            Use this method when an ID is required for the operation.
            For optional ID access, use get_id() instead.
        """
        message_id = getattr(self, "id", None)
        if message_id is None:
            msg = "Message does not have an ID. Messages only have IDs after being stored in the database."
            raise ValueError(msg)
        return message_id


class DefaultModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )

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
    context_id: str | None = None
    text: str
    files: list[str] = []
    edit: bool
    duration: float | None = None

    properties: Properties | None = None
    category: str | None = None
    content_blocks: list[ContentType | ContentBlock] | None = None
    session_metadata: dict | None = None

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        if isinstance(v, list):
            return [cls.validate_content_blocks(block) for block in v]
        if isinstance(v, dict):
            # Flat ContentType (has "type" but no "contents") vs grouped ContentBlock
            if "type" in v and "contents" not in v:
                return _CONTENT_TYPE_ADAPTER.validate_python(v)
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
        if not message.sender or not message.sender_name:
            msg = "The message does not have the required fields (sender, sender_name)."
            raise ValueError(msg)
        text = message.text
        if not isinstance(text, str):
            text = ""
        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=text,
            session_id=message.session_id,
            context_id=message.context_id,
            files=message.files or [],
            timestamp=message.timestamp,
            flow_id=flow_id,
            edit=message.edit,
            content_blocks=message.content_blocks,
            properties=message.properties,
            category=message.category,
            session_metadata=getattr(message, "session_metadata", None),
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
            reason = f"{exception._message()}\n" if callable(exception._message) else f"{exception._message}\n"  # noqa: SLF001
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
        context_id: str | None = None,
        source: Source | None = None,
        trace_name: str | None = None,
        flow_id: UUID | str | None = None,
        session_metadata: dict | None = None,
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
            context_id=context_id,
            sender=source.display_name if source else None,
            sender_name=source.display_name if source else None,
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
                TextContent(text=plain_reason),
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
                ),
            ],
            flow_id=flow_id,
            session_metadata=session_metadata,
        )


__all__ = ["ContentBlock", "DefaultModel", "ErrorMessage", "Message", "MessageResponse"]
