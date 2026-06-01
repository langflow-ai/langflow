from __future__ import annotations

import asyncio
import json
import re
import traceback
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from pathlib import Path
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
from lfx.schema.validators import str_to_timestamp_validator, timestamp_to_str, timestamp_to_str_validator
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER
from lfx.utils.image import create_image_content_dict
from lfx.utils.mustache_security import safe_mustache_render
from lfx.utils.secrets import is_secret_value

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame

MAX_ATTACHMENT_SIZE_BYTES: int = 50 * 1024 * 1024

_CONTENT_TYPE_ADAPTER = TypeAdapter(ContentType)


def _is_text_like_extension(file_path: Any) -> bool:
    """Return True for files whose extension we recognize as plain text / structured text.

    Used as a guard before falling back to latin-1 decoding in
    ``get_file_content_dicts`` — see ``read_text_file`` for the encoding chain.
    Files with no extension are treated as text-like so callers passing CLI-style
    stdin captures or extension-less plain text continue to work.
    """
    from lfx.base.data.utils import TEXT_FILE_TYPES

    try:
        suffix = Path(file_path).suffix.lstrip(".").lower()
    except (OSError, TypeError, ValueError):
        return False
    if not suffix:
        return True
    return suffix in TEXT_FILE_TYPES


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
    run_id: str | UUID | None = Field(default=None)
    timestamp: Annotated[str, timestamp_to_str_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f %Z")
    )
    flow_id: str | UUID | None = None
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

    properties: Properties = Field(default_factory=Properties)
    category: Literal["message", "error", "warning", "info"] | None = "message"
    content_blocks: list[ContentType] = Field(default_factory=list)
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
        """Replace text content or set a stream for later consumption.

        Drops every existing TextContent in ``content_blocks`` and, if
        ``value`` is non-empty, appends a single TextContent at the end.
        Non-text blocks keep their position so ``content_blocks`` reflects
        chronological order: tool calls / reasoning / media first, final
        text last.
        """
        if isinstance(value, AsyncIterator | Iterator):
            # Drop any existing TextContent (and the data["text"] mirror) so the
            # getter doesn't return stale prior-round text while the stream sits
            # unconsumed. Non-text blocks keep their position.
            non_text = [b for b in self.content_blocks if not isinstance(b, TextContent)]
            object.__setattr__(self, "content_blocks", non_text)
            self.data[self.text_key] = ""
            object.__setattr__(self, "_text_stream", value)
            return
        # Clear any pending/exhausted stream
        self.__dict__.pop("_text_stream", None)
        non_text = [b for b in self.content_blocks if not isinstance(b, TextContent)]
        if value:
            object.__setattr__(self, "content_blocks", [*non_text, TextContent(text=str(value))])
        else:
            object.__setattr__(self, "content_blocks", non_text)
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

    @field_validator("run_id", mode="before")
    @classmethod
    def validate_run_id(cls, value):
        if isinstance(value, UUID):
            value = str(value)
        return value

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value):
        if is_secret_value(value):
            return str(value)
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
            # Dict -- discriminator handles every ContentType (including the
            # grouped ContentBlock with type="group"). Legacy JSON without
            # an explicit "type" but with title+contents still validates as
            # a ContentBlock for backwards compat.
            if isinstance(item, dict):
                if "type" in item:
                    return _CONTENT_TYPE_ADAPTER.validate_python(item)
                if "title" in item and "contents" in item:
                    return ContentBlock.model_validate(item)
                return _CONTENT_TYPE_ADAPTER.validate_python(item)
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

    @field_serializer("run_id")
    def serialize_run_id(self, value):
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        return timestamp_to_str(value)

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
        # Sync self.data["text"] from content_blocks when content_blocks has
        # text content. Otherwise preserve whatever the caller passed in,
        # including an explicit ``None`` — downstream code (e.g.
        # ``MessageTable.from_message``) uses ``None`` vs ``""`` to tell
        # "missing required field" apart from "intentionally empty input."
        text_from_blocks = "".join(b.text for b in self.content_blocks if isinstance(b, TextContent))
        if text_from_blocks:
            self.data[self.text_key] = text_from_blocks
        elif self.text_key in self.data:
            existing = self.data[self.text_key]
            if existing is not None and not isinstance(existing, str):
                self.data[self.text_key] = ""

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

        from lfx.schema.content_types import ImageContent, ToolContent

        blocks: list[Any] = []
        content = lc_message.content
        if isinstance(content, str):
            if content:
                blocks.append(TextContent(text=content))
        else:
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
                        # ``source`` can be missing OR explicitly None on
                        # malformed payloads; guard both cases (``.get(key, {})``
                        # only defaults when the key is absent, not when it's
                        # explicitly None).
                        source = item.get("source") or {}
                        url = item.get("url") or source.get("url", "")
                        b64 = source.get("data") or item.get("base64")
                        mime = source.get("media_type") or item.get("mime_type")
                        if b64 and mime:
                            blocks.append(ImageContent(base64=b64, mime_type=mime))
                        elif url:
                            blocks.append(ImageContent(urls=[url]))
                    elif item_type == "tool_use":
                        # Anthropic raw content carries tool calls inline as
                        # ``{"type":"tool_use","id","name","input"}``. LangChain
                        # leaves ``.tool_calls`` empty for raw-content messages,
                        # so the tool_calls fallback below won't fire — capture
                        # them here so chat-history round-trips don't drop the
                        # call.
                        blocks.append(
                            ToolContent(
                                name=item.get("name", ""),
                                tool_input=item.get("input", {}),
                                id=item.get("id"),
                            )
                        )
                    else:
                        logger.debug(f"from_lc_message: skipping unsupported content type '{item_type}'")

        # Tool calls and usage metadata live as AIMessage attributes, not in
        # ``content``. Tool-calling agents typically emit ``content=""`` with
        # only ``tool_calls`` set, so this must run regardless of content shape.
        if hasattr(lc_message, "tool_calls") and lc_message.tool_calls:
            # The content walk above may have already captured tool_use blocks
            # (Anthropic raw content). Skip ids already present so a message
            # carrying both inline tool_use and a populated ``.tool_calls``
            # doesn't double the same logical call.
            seen_tool_ids = {b.id for b in blocks if isinstance(b, ToolContent) and b.id}
            # ``tc["id"]`` is LangChain's stable ``tool_call_id``: same value
            # at start, during args streaming, and on the result, so the same
            # logical tool call dedups to one ``ToolContent`` across re-fires.
            blocks.extend(
                ToolContent(name=tc.get("name", ""), tool_input=tc.get("args", {}), id=tc.get("id"))
                for tc in lc_message.tool_calls
                if tc.get("id") not in seen_tool_ids
            )

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

        # Preserve the text-only fast path: a string-content message with no
        # tool calls or usage data keeps ``content_blocks=[]`` (frontend
        # compat) and routes content through the ``text=`` parameter.
        if isinstance(content, str) and not any(not isinstance(b, TextContent) for b in blocks):
            return cls(text=content, sender=sender, sender_name=sender_name)
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
        # Safely extract optional fields that may not exist on a plain Data object.
        # ``run_id`` and ``session_metadata`` are not present on the base ``Data``
        # class but are copied when the source is a ``Message`` so message
        # provenance round-trips through ``Message.from_data(msg.to_data())``.
        for field in (
            "sender",
            "sender_name",
            "files",
            "session_id",
            "context_id",
            "run_id",
            "timestamp",
            "flow_id",
            "error",
            "edit",
            "session_metadata",
        ):
            try:
                value = getattr(data, field)
                kwargs[field] = value
            except AttributeError:
                pass
        return cls(**kwargs)

    # Keep this async method for backwards compatibility
    def get_file_content_dicts(self, model_name: str | None = None):
        def _safe_attachment_name(value: Any) -> str | None:
            if isinstance(value, Image):
                if not value.path:
                    return None
                try:
                    return Path(value.path).name
                except (OSError, TypeError, ValueError):
                    return None
            try:
                return Path(value).name
            except (OSError, TypeError, ValueError):
                return None

        content_dicts = []
        try:
            files = get_file_paths(self.files)
        except (OSError, TypeError, ValueError) as exc:
            logger.error(
                "Error getting file paths",
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return content_dicts

        for file in files:
            if isinstance(file, Image):
                content_dicts.append(file.to_content_dict(flow_id=self.flow_id))
                continue

            try:
                if is_image_file(file):
                    content_dicts.append(create_image_content_dict(file, None, model_name))
                    continue

                # Refuse to text-decode files whose extension is not in
                # TEXT_FILE_TYPES (and that didn't pass is_image_file above).
                # `read_text_file` falls back to latin-1 which ALWAYS succeeds,
                # so binary payloads (e.g. a PNG that PIL refused to verify)
                # used to slip through and get injected into the HumanMessage
                # as a long latin-1-garbled string (QA API-010).
                if not _is_text_like_extension(file):
                    logger.debug(
                        "Skipping attachment during message conversion: unsupported binary extension",
                        file_name=_safe_attachment_name(file),
                    )
                    continue

                try:
                    file_size_bytes = Path(file).stat().st_size
                except (OSError, ValueError) as exc:
                    logger.warning(
                        "Skipping attachment during message conversion: could not stat file",
                        error_type=type(exc).__name__,
                        file_name=_safe_attachment_name(file),
                    )
                    continue

                if file_size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
                    continue

                from lfx.base.data.utils import parse_text_file_to_data

                parsed_file = parse_text_file_to_data(file, silent_errors=True)
                parsed_data = parsed_file.data if parsed_file else {}
                parsed_text = parsed_data.get("text") if isinstance(parsed_data, dict) else None
                if not parsed_text:
                    continue

                parsed_text_str = parsed_text if isinstance(parsed_text, str) else json.dumps(parsed_text)
                file_name = _safe_attachment_name(file) or "attachment"
                # Avoid the literal "Attachment:" framing — Gemini 2.5 Flash
                # (and likely related models) treats it as a multimodal-attach
                # request and refuses with "I cannot process attachments in
                # this environment" (QA GAP-M-3). A neutral "File … contents"
                # header keeps the same context for the LLM without tripping
                # provider refusal heuristics.
                content_dicts.append(
                    {
                        "type": "text",
                        "text": f"File '{file_name}' contents:\n{parsed_text_str}",
                    }
                )
            except PermissionError as exc:
                logger.error(
                    "Skipping attachment during message conversion: permission denied",
                    error_type=type(exc).__name__,
                    file_name=_safe_attachment_name(file),
                    exc_info=True,
                )
                continue
            except (FileNotFoundError, UnicodeDecodeError, ValueError, OSError) as exc:
                logger.warning(
                    "Skipping unsupported attachment during message conversion",
                    error_type=type(exc).__name__,
                    file_name=_safe_attachment_name(file),
                )
                continue
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
    # ``Message.timestamp`` is a string with microsecond+timezone precision
    # (``%Y-%m-%d %H:%M:%S.%f %Z``) which Pydantic's default datetime parser
    # rejects. Reuse the shared parser so MessageResponse.from_message
    # accepts any of the formats ``Message`` itself recognises.
    timestamp: Annotated[datetime, str_to_timestamp_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
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
    # ContentBlock joined the ContentType discriminated union as tag "group",
    # so list[ContentType] alone covers both flat ContentType (text, image,
    # tool_use, ...) and the wrapping ContentBlock shape. The previous
    # `list[ContentType | ContentBlock]` union confused Pydantic's
    # discriminator: any dict with a `contents` field (which every backend
    # BaseContent now serializes by default, even as []) was routed to
    # ContentBlock and rejected with `type: literal_error` for non-group
    # types like text.
    content_blocks: list[ContentType] | None = None
    session_metadata: dict | None = None

    @field_validator("content_blocks", mode="before")
    @classmethod
    def validate_content_blocks(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        if isinstance(v, list):
            return [cls.validate_content_blocks(block) for block in v]
        if isinstance(v, dict):
            # The discriminator on `type` handles flat ContentType vs grouped
            # ContentBlock uniformly. The old "type and not contents"
            # heuristic broke once BaseContent started serializing
            # `contents: []` on every leaf.
            return _CONTENT_TYPE_ADAPTER.validate_python(v)
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
        # first check if the record has all the required fields. ``message.text``
        # is a computed_field over content_blocks now, so it always returns a
        # string. The "content present" signal is: ``data["text"]`` explicitly
        # set (covers ``text=""`` from ChatInput), or a pending text stream
        # (iterator), or any ``content_blocks`` entries (covers tool-call-only
        # / media-only agent messages whose ``content_blocks`` carry the
        # whole payload).
        no_content = message.data.get("text") is None and message.text_stream is None and not message.content_blocks
        if no_content or not message.sender or not message.sender_name:
            msg = "The message does not have the required fields (text, sender, sender_name)."
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


__all__ = [
    "MAX_ATTACHMENT_SIZE_BYTES",
    "ContentBlock",
    "DefaultModel",
    "ErrorMessage",
    "Message",
    "MessageResponse",
]
