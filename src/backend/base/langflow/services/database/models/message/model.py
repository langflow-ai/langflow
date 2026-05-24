import json
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from fastapi.encoders import jsonable_encoder
from pydantic import ConfigDict, field_serializer, field_validator
from sqlalchemy import Index, Text, text
from sqlmodel import JSON, Column, Field, SQLModel

from langflow.schema.content_block import ContentBlock
from langflow.schema.properties import Properties
from langflow.schema.validators import TF_WITH_TZ_AND_MICROSECONDS, str_to_timestamp, str_to_timestamp_validator

if TYPE_CHECKING:
    from langflow.schema.message import Message


class MessageBase(SQLModel):
    timestamp: Annotated[datetime, str_to_timestamp_validator] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sender: str
    sender_name: str
    session_id: str
    context_id: str | None = Field(default=None)
    text: str = Field(sa_column=Column(Text))
    files: list[str] = Field(default_factory=list)
    error: bool = Field(default=False)
    edit: bool = Field(default=False)

    properties: Properties = Field(default_factory=Properties)
    category: str = Field(default="message")
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    session_metadata: dict | None = Field(default=None)

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.strftime(TF_WITH_TZ_AND_MICROSECONDS)

        if isinstance(value, str):
            dt = str_to_timestamp(value)  # unified, UTC-normalized
            return dt.strftime(TF_WITH_TZ_AND_MICROSECONDS)

        return value

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        return value or []

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value):
        if isinstance(value, UUID):
            return str(value)
        return value

    @classmethod
    def from_message(cls, message: "Message", flow_id: str | UUID | None = None, run_id: str | UUID | None = None):
        if message.text is None or not message.sender or not message.sender_name:
            msg = "The message does not have the required fields (text, sender, sender_name)."
            raise ValueError(msg)

        if message.files:
            image_paths = []
            for file in message.files:
                if hasattr(file, "path") and hasattr(file, "url") and file.path:
                    session_id = message.session_id
                    if session_id and str(session_id) in file.path:
                        parts = file.path.split(str(session_id))
                        if len(parts) > 1:
                            image_paths.append(f"{session_id}{parts[1]}")
                        else:
                            image_paths.append(file.path)
                    else:
                        image_paths.append(file.path)
                elif isinstance(file, str):
                    image_paths.append(file)

            if image_paths:
                message.files = image_paths

        if isinstance(message.timestamp, str):
            # Convert timestamp string in format "YYYY-MM-DD HH:MM:SS.ffffff UTC" to datetime
            try:
                timestamp = datetime.strptime(message.timestamp, TF_WITH_TZ_AND_MICROSECONDS).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                # Fallback for ISO format if the above fails; astimezone preserves offset if present
                parsed = datetime.fromisoformat(message.timestamp)
                timestamp = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        else:
            timestamp = message.timestamp

        if not flow_id and message.flow_id:
            flow_id = message.flow_id
        if not run_id and getattr(message, "run_id", None):
            run_id = message.run_id

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

        if isinstance(run_id, str):
            try:
                run_id = UUID(run_id)
            except ValueError as exc:
                msg = f"Run ID {run_id} is not a valid UUID"
                raise ValueError(msg) from exc

        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message_text,
            session_id=message.session_id,
            context_id=message.context_id,
            files=message.files or [],
            timestamp=timestamp,
            flow_id=flow_id,
            run_id=run_id,
            properties=properties,
            category=message.category,
            content_blocks=content_blocks,
            session_metadata=getattr(message, "session_metadata", None),
        )


class MessageTable(MessageBase, table=True):  # type: ignore[call-arg]
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    __tablename__ = "message"
    __table_args__ = (
        Index(
            "ix_message_session_metadata_tenant",
            text("(session_metadata->>'tenant_id')"),
            postgresql_using="btree",
        ),
        Index(
            "ix_message_session_metadata_user",
            text("(session_metadata->>'user_id')"),
            postgresql_using="btree",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID | None = Field(default=None)
    run_id: UUID | None = Field(default=None, index=True)
    is_output: bool = Field(default=False)

    files: list[str] = Field(sa_column=Column(JSON))
    properties: dict | Properties = Field(  # type: ignore[assignment]
        default_factory=lambda: Properties().model_dump(),
        sa_column=Column(JSON),
    )
    category: str = Field(sa_column=Column(Text))
    content_blocks: list[dict | ContentBlock] = Field(  # type: ignore[assignment]
        default_factory=list,
        sa_column=Column(JSON),
    )

    # Enterprise session metadata - flexible JSON column for client-provided context
    session_metadata: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Session context data (e.g., user roles, custom tags, or analytics data).",
    )

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return UUID(value)
        return value

    @staticmethod
    def _sanitize_json(value):
        """Coerce values into a JSON-safe shape before they reach the SQL UPDATE.

        Replaces float NaN/Infinity with None to avoid PostgreSQL jsonb rejection,
        and resolves non-serializable Python objects (notably pandas DataFrame /
        lfx Table instances and numpy scalars) that can leak into ContentBlock
        fields when an upstream component output — e.g. the Memory Base
        ``retrieve_data`` Table — is captured by message tracking before the
        consumer (Parser) has converted it to text.
        """
        # numpy scalars (np.float64, np.int64, np.bool_, ...) survive
        # ``jsonable_encoder`` when nested inside a DataFrame-derived dict
        # and would later be rejected by the jsonb encoder. Coerce them to
        # their Python-native counterparts so persistence succeeds. This must
        # come before the ``float`` / ``int`` / ``bool`` checks because numpy
        # scalars inherit from those Python types.
        if isinstance(value, np.generic):
            return MessageTable._sanitize_json(value.item())

        if isinstance(value, bool):
            return value

        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return value

        if isinstance(value, dict):
            return {k: MessageTable._sanitize_json(v) for k, v in value.items()}

        if isinstance(value, list):
            return [MessageTable._sanitize_json(v) for v in value]

        if isinstance(value, pd.DataFrame):
            return [MessageTable._sanitize_json(record) for record in value.to_dict(orient="records")]

        if value is None or isinstance(value, str | int):
            return value

        # Unknown type — coerce to a JSON-safe representation rather than
        # letting it propagate to the SQL UPDATE and fail persistence.
        try:
            encoded = jsonable_encoder(value)
        except (TypeError, ValueError):
            return str(value)
        if encoded is value:
            return str(value)
        return MessageTable._sanitize_json(encoded)

    @field_validator("properties", "content_blocks", "session_metadata", mode="before")
    @classmethod
    def validate_properties_or_content_blocks(cls, value):
        if isinstance(value, list):
            value = [cls.validate_properties_or_content_blocks(item) for item in value]
        elif hasattr(value, "model_dump"):
            value = value.model_dump()
        elif isinstance(value, str):
            value = json.loads(value)

        return cls._sanitize_json(value)

    @field_serializer("properties", "content_blocks", "session_metadata")
    @classmethod
    def serialize_properties_or_content_blocks(cls, value) -> dict | list[dict]:
        # Redundant sanitization here acts as a defensive measure for rows
        # already in the database that might contain NaN/Infinity values.
        if isinstance(value, list):
            value = [cls.serialize_properties_or_content_blocks(item) for item in value]
        elif hasattr(value, "model_dump"):
            value = value.model_dump()
        elif isinstance(value, str):
            value = json.loads(value)

        return cls._sanitize_json(value)


class MessageRead(MessageBase):
    id: UUID
    flow_id: UUID | None = None
    session_metadata: dict | None = None
    run_id: UUID | None = None


class MessageCreate(MessageBase):
    session_metadata: dict | None = None


class MessageUpdate(SQLModel):
    text: str | None = None
    sender: str | None = None
    sender_name: str | None = None
    session_id: str | None = None
    context_id: str | None = None
    files: list[str] | None = None
    edit: bool | None = None
    error: bool | None = None
    properties: Properties | None = None
    session_metadata: dict | None = None
    category: str | None = None
    content_blocks: list[ContentBlock] | None = None
