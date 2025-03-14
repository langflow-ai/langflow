# Path: src/backend/langflow/services/database/models/flow/model.py

import re
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

import emoji
from emoji import purely_emoji
from fastapi import HTTPException, status
from loguru import logger
from pydantic import (
    BaseModel,
    ValidationInfo,
    field_serializer,
    field_validator,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Text, UniqueConstraint, text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.schema import Data

if TYPE_CHECKING:
    from langflow.services.database.models import TransactionTable
    from langflow.services.database.models.folder import Folder
    from langflow.services.database.models.message import MessageTable
    from langflow.services.database.models.user import User
    from langflow.services.database.models.vertex_builds.model import VertexBuildTable

HEX_COLOR_LENGTH = 7


class AccessTypeEnum(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class FlowBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = Field(default=None, sa_column=Column(Text, index=True, nullable=True))
    icon: str | None = Field(default=None, nullable=True)
    icon_bg_color: str | None = Field(default=None, nullable=True)
    gradient: str | None = Field(default=None, nullable=True)
    data: dict | None = Field(default=None, nullable=True)
    is_component: bool | None = Field(default=False, nullable=True)
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=True)
    webhook: bool | None = Field(default=False, nullable=True, description="Can be used on the webhook endpoint")
    endpoint_name: str | None = Field(default=None, nullable=True, index=True)
    tags: list[str] | None = None
    locked: bool | None = Field(default=False, nullable=True)
    access_type: AccessTypeEnum = Field(
        default=AccessTypeEnum.PRIVATE,
        sa_column=Column(
            SQLEnum(
                AccessTypeEnum,
                name="access_type_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'private'"),
        ),
    )

    @field_validator("endpoint_name")
    @classmethod
    def validate_endpoint_name(cls, v):
        # Endpoint name must be a string containing only letters, numbers, hyphens, and underscores
        if v is not None:
            if not isinstance(v, str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Endpoint name must be a string",
                )
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Endpoint name must contain only letters, numbers, hyphens, and underscores",
                )
        return v

    @field_validator("icon_bg_color")
    @classmethod
    def validate_icon_bg_color(cls, v):
        if v is not None and not isinstance(v, str):
            msg = "Icon background color must be a string"
            raise ValueError(msg)
        # validate that is is a hex color
        if v and not v.startswith("#"):
            msg = "Icon background color must start with #"
            raise ValueError(msg)

        # validate that it is a valid hex color
        if v and len(v) != HEX_COLOR_LENGTH:
            msg = "Icon background color must be 7 characters long"
            raise ValueError(msg)
        return v

    @field_validator("icon")
    @classmethod
    def validate_icon_atr(cls, v):
        #   const emojiRegex = /\p{Emoji}/u;
        # const isEmoji = emojiRegex.test(data?.node?.icon!);
        # emoji pattern in Python
        if v is None:
            return v
        # we are going to use the emoji library to validate the emoji
        # emojis can be defined using the :emoji_name: syntax

        if not v.startswith(":") and not v.endswith(":"):
            return v
        if not v.startswith(":") or not v.endswith(":"):
            # emoji should have both starting and ending colons
            # so if one of them is missing, we will raise
            msg = f"Invalid emoji. {v} is not a valid emoji."
            raise ValueError(msg)

        emoji_value = emoji.emojize(v, variant="emoji_type")
        if v == emoji_value:
            logger.warning(f"Invalid emoji. {v} is not a valid emoji.")
        icon = emoji_value

        if purely_emoji(icon):
            # this is indeed an emoji
            return icon
        # otherwise it should be a valid lucide icon
        if v is not None and not isinstance(v, str):
            msg = "Icon must be a string"
            raise ValueError(msg)
        # is should be lowercase and contain only letters and hyphens
        if v and not v.islower():
            msg = "Icon must be lowercase"
            raise ValueError(msg)
        if v and not v.replace("-", "").isalpha():
            msg = "Icon must contain only letters and hyphens"
            raise ValueError(msg)
        return v

    @field_validator("data")
    @classmethod
    def validate_json(cls, v):
        if not v:
            return v
        if not isinstance(v, dict):
            msg = "Flow must be a valid JSON"
            raise ValueError(msg)  # noqa: TRY004

        # data must contain nodes and edges
        if "nodes" not in v:
            msg = "Flow must have nodes"
            raise ValueError(msg)
        if "edges" not in v:
            msg = "Flow must have edges"
            raise ValueError(msg)

        return v

    # updated_at can be serialized to JSON
    @field_serializer("updated_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            # I'm getting 2024-05-29T17:57:17.631346
            # and I want 2024-05-29T17:57:17-05:00
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value

    @field_validator("updated_at", mode="before")
    @classmethod
    def validate_dt(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v

        return datetime.fromisoformat(v)


class Flow(FlowBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    user_id: UUID | None = Field(index=True, foreign_key="user.id", nullable=True)
    user: "User" = Relationship(back_populates="flows")
    icon: str | None = Field(default=None, nullable=True)
    tags: list[str] | None = Field(sa_column=Column(JSON), default=[])
    locked: bool | None = Field(default=False, nullable=True)
    folder_id: UUID | None = Field(default=None, foreign_key="folder.id", nullable=True, index=True)
    fs_path: str | None = Field(default=None, nullable=True)
    folder: Optional["Folder"] = Relationship(back_populates="flows")
    messages: list["MessageTable"] = Relationship(back_populates="flow")
    transactions: list["TransactionTable"] = Relationship(back_populates="flow")
    vertex_builds: list["VertexBuildTable"] = Relationship(back_populates="flow")

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "data": serialized.pop("data"),
            "name": serialized.pop("name"),
            "description": serialized.pop("description"),
            "updated_at": serialized.pop("updated_at"),
        }
        return Data(data=data)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_flow_name"),
        UniqueConstraint("user_id", "endpoint_name", name="unique_flow_endpoint_name"),
    )


class FlowCreate(FlowBase):
    user_id: UUID | None = None
    folder_id: UUID | None = None
    fs_path: str | None = None


class FlowRead(FlowBase):
    id: UUID
    user_id: UUID | None = Field()
    folder_id: UUID | None = Field()
    tags: list[str] | None = Field(None, description="The tags of the flow")


class FlowHeader(BaseModel):
    """Model representing a header for a flow - Without the data."""

    id: UUID = Field(description="Unique identifier for the flow")
    name: str = Field(description="The name of the flow")
    folder_id: UUID | None = Field(
        None,
        description="The ID of the folder containing the flow. None if not associated with a folder",
    )
    is_component: bool | None = Field(None, description="Flag indicating whether the flow is a component")
    endpoint_name: str | None = Field(None, description="The name of the endpoint associated with this flow")
    description: str | None = Field(None, description="A description of the flow")
    data: dict | None = Field(None, description="The data of the component, if is_component is True")
    access_type: AccessTypeEnum | None = Field(None, description="The access type of the flow")
    tags: list[str] | None = Field(None, description="The tags of the flow")

    @field_validator("data", mode="before")
    @classmethod
    def validate_flow_header(cls, value: dict, info: ValidationInfo):
        if not info.data["is_component"]:
            return None
        return value


class FlowUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    data: dict | None = None
    folder_id: UUID | None = None
    endpoint_name: str | None = None
    locked: bool | None = None
    access_type: AccessTypeEnum | None = None
    fs_path: str | None = None

    @field_validator("endpoint_name")
    @classmethod
    def validate_endpoint_name(cls, v):
        # Endpoint name must be a string containing only letters, numbers, hyphens, and underscores
        if v is not None:
            if not isinstance(v, str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Endpoint name must be a string",
                )
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Endpoint name must contain only letters, numbers, hyphens, and underscores",
                )
        return v
