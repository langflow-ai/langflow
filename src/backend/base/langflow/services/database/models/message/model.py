import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid4

from litellm import ConfigDict
from pydantic import field_serializer, field_validator
from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, SQLModel

from langflow.schema.content_block import ContentBlock
from langflow.schema.properties import Properties
from langflow.schema.validators import str_to_timestamp_validator

if TYPE_CHECKING:
    from langflow.schema.message import Message


class MessageBase(SQLModel):
    timestamp: Annotated[datetime, str_to_timestamp_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sender: str
    sender_name: str
    session_id: str
    text: str = Field(sa_column=Column(Text))
    files: list[str] = Field(default_factory=list)
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

    properties: Properties = Field(default_factory=Properties)
    category: str = Field(default="message")
    content_blocks: list[ContentBlock] = Field(default_factory=list)

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.strftime("%Y-%m-%d %H:%M:%S %Z")
        if isinstance(value, str):
            # Make sure the timestamp is in UTC
            value = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
            return value.strftime("%Y-%m-%d %H:%M:%S %Z")
        return value

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        if not value:
            value = []
        return value

    @classmethod
    def from_message(cls, message: "Message", flow_id: str | UUID | None = None):
        # first check if the record has all the required fields
        if message.text is None or not message.sender or not message.sender_name:
            msg = "The message does not have the required fields (text, sender, sender_name)."
            raise ValueError(msg)
        if message.files:
            image_paths = []
            for file in message.files:
                if hasattr(file, "path") and hasattr(file, "url") and file.path:
                    session_id = message.session_id
                    if session_id:
                        image_paths.append(f"{session_id}{file.path.split(str(session_id))[1]}")
                    else:
                        image_paths.append(file.path)
            if image_paths:
                message.files = image_paths

        if isinstance(message.timestamp, str):
            # Convert timestamp string in format "YYYY-MM-DD HH:MM:SS UTC" to datetime
            try:
                timestamp = datetime.strptime(message.timestamp, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except ValueError:
                # Fallback for ISO format if the above fails
                timestamp = datetime.fromisoformat(message.timestamp).replace(tzinfo=timezone.utc)
        else:
            timestamp = message.timestamp
        if not flow_id and message.flow_id:
            flow_id = message.flow_id
        # If the text is not a string, it means it could be
        # async iterator so we simply add it as an empty string
        message_text = "" if not isinstance(message.text, str) else message.text

        properties = (
            message.properties.model_dump_json()
            if hasattr(message.properties, "model_dump_json")
            else message.properties
        )
        content_blocks = []
        for content_block in message.content_blocks or []:
            content = content_block.model_dump_json() if hasattr(content_block, "model_dump_json") else content_block
            content_blocks.append(content)

        if isinstance(flow_id, str):
            try:
                flow_id = UUID(flow_id)
            except ValueError as exc:
                msg = f"Flow ID {flow_id} is not a valid UUID"
                raise ValueError(msg) from exc

        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message_text,
            session_id=message.session_id,
            files=message.files or [],
            timestamp=timestamp,
            flow_id=flow_id,
            properties=properties,
            category=message.category,
            content_blocks=content_blocks,
        )


class MessageTable(MessageBase, table=True):  # type: ignore[call-arg]
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
    __tablename__ = "message"
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    flow_id: UUID | None = Field(default=None)
    files: list[str] = Field(sa_column=Column(JSON))
    properties: dict | Properties = Field(default_factory=lambda: Properties().model_dump(), sa_column=Column(JSON))  # type: ignore[assignment]
    category: str = Field(sa_column=Column(Text))
    content_blocks: list[dict | ContentBlock] = Field(default_factory=list, sa_column=Column(JSON))  # type: ignore[assignment]

    # We need to make sure the datetimes have timezone after running session.refresh
    # because we are losing the timezone information when we save the message to the database
    # and when we read it back. We use field_validator to make sure the datetimes have timezone
    # after running session.refresh

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value

    @field_validator("properties", "content_blocks", mode="before")
    @classmethod
    def validate_properties_or_content_blocks(cls, value):
        if isinstance(value, list):
            return [cls.validate_properties_or_content_blocks(item) for item in value]
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, str):
            return json.loads(value)
        return value

    @field_serializer("properties", "content_blocks")
    @classmethod
    def serialize_properties_or_content_blocks(cls, value) -> dict | list[dict]:
        if isinstance(value, list):
            return [cls.serialize_properties_or_content_blocks(item) for item in value]
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, str):
            return json.loads(value)
        return value


class MessageRead(MessageBase):
    id: UUID
    flow_id: UUID | None = Field()


class MessageCreate(MessageBase):
    pass


class MessageUpdate(SQLModel):
    text: str | None = None
    sender: str | None = None
    sender_name: str | None = None
    session_id: str | None = None
    files: list[str] | None = None
    edit: bool | None = None
    error: bool | None = None
    properties: Properties | None = None
