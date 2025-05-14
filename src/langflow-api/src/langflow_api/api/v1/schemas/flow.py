import re
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator


class AccessTypeEnum(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class FlowBase(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    gradient: str | None = None
    data: dict | None = None
    is_component: bool | None = False
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    webhook: bool | None = False
    endpoint_name: str | None = None
    tags: list[str] | None = None
    locked: bool | None = False
    mcp_enabled: bool | None = False
    action_name: str | None = None
    action_description: str | None = None
    access_type: AccessTypeEnum = AccessTypeEnum.PRIVATE

    @field_validator("endpoint_name")
    @classmethod
    def validate_endpoint_name(cls, v):
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("Endpoint name must be a string")
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise ValueError("Endpoint name must contain only letters, numbers, hyphens, and underscores")
        return v

    @field_validator("icon_bg_color")
    @classmethod
    def validate_icon_bg_color(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("Icon background color must be a string")
        if v and not v.startswith("#"):
            raise ValueError("Icon background color must start with #")
        if v and len(v) != 7:
            raise ValueError("Icon background color must be 7 characters long")
        return v

    @field_validator("icon")
    @classmethod
    def validate_icon_atr(cls, v):
        if v is None:
            return v
        # Add your emoji/lucide validation logic here if needed
        return v

    @field_validator("data")
    @classmethod
    def validate_json(cls, v):
        if not v:
            return v
        if not isinstance(v, dict):
            raise ValueError("Flow must be a valid JSON")
        if "nodes" not in v:
            raise ValueError("Flow must have nodes")
        if "edges" not in v:
            raise ValueError("Flow must have edges")
        return v

    @field_serializer("updated_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
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


class Flow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    data: dict | None = None
    user_id: UUID | None = None
    icon: str | None = None
    tags: list[str] | None = Field(default_factory=list)
    locked: bool | None = False
    folder_id: UUID | None = None
    fs_path: str | None = None

    class Config:
        orm_mode = True

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "data": serialized.pop("data"),
            "name": serialized.pop("name", None),
            "description": serialized.pop("description", None),
            "updated_at": serialized.pop("updated_at", None),
        }
        return data  # or Data(data=data) if you have a Data model


class FlowCreate(FlowBase):
    user_id: str | None = None
    folder_id: str | None = None
    fs_path: str | None = None


class FlowRead(FlowBase):
    id: str
    user_id: str | None = None
    folder_id: str | None = None
    tags: list[str] | None = Field(None, description="The tags of the flow")


class FlowListCreate(BaseModel):
    flows: list[FlowCreate]


class FlowDataRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    viewport: dict | None = None


class CancelFlowResponse(BaseModel):
    success: bool
    message: str
