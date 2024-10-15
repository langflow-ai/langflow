from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.schema.message import Message
    from langflow.services.database.models.flow.model import Flow


class MessageBase(SQLModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender: str
    sender_name: str
    session_id: str
    text: str = Field(sa_column=Column(Text))
    files: list[str] = Field(default_factory=list)
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

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
                    image_paths.append(f"{session_id}{file.path.split(session_id)[1]}")
            if image_paths:
                message.files = image_paths

        if isinstance(message.timestamp, str):
            # The message.timestamp is created using strftime("%Y-%m-%dT%H:%M:%S").
            # This format is not fully ISO 8601 compliant because it lacks timezone information.
            # Aadd timezone info (UTC) back to the timestamp here.
            timestamp = datetime.fromisoformat(message.timestamp).replace(tzinfo=timezone.utc)
        else:
            timestamp = message.timestamp
        if not flow_id and message.flow_id:
            flow_id = message.flow_id
        # If the text is not a string, it means it could be
        # async iterator so we simply add it as an empty string
        message_text = "" if not isinstance(message.text, str) else message.text
        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message_text,
            session_id=message.session_id,
            files=message.files or [],
            timestamp=timestamp,
            flow_id=flow_id,
        )


class MessageTable(MessageBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "message"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID | None = Field(default=None, foreign_key="flow.id")
    flow: "Flow" = Relationship(back_populates="messages")
    files: list[str] = Field(sa_column=Column(JSON))

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value

    # Needed for Column(JSON)
    class Config:
        arbitrary_types_allowed = True


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
