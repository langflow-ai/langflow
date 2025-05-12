from ast import Dict
from enum import Enum
from pydantic import BaseModel, Field, field_serializer, field_validator
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone

from langflow_api.api.v2.schemas.common import ResultDataResponse


class AccessTypeEnum(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class FlowBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    icon_bg_color: Optional[str] = None
    gradient: Optional[str] = None
    data: Optional[Dict] = None
    is_component: Optional[bool] = False
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    webhook: Optional[bool] = False
    endpoint_name: Optional[str] = None
    tags: Optional[List[str]] = None
    locked: Optional[bool] = False
    mcp_enabled: Optional[bool] = False
    action_name: Optional[str] = None
    action_description: Optional[str] = None
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

class FlowCreate(FlowBase):
    user_id: Optional[str] = None  # Use UUID if you want
    folder_id: Optional[str] = None
    fs_path: Optional[str] = None


class FlowRead(FlowBase):
    id: str  # Use UUID if you want
    user_id: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = Field(None, description="The tags of the flow")


class FlowListCreate(BaseModel):
    flows: list[FlowCreate]

class FlowListIds(BaseModel):
    flow_ids: list[str]

class FlowListRead(BaseModel):
    flows: list[FlowRead]

class FlowListReadWithFolderName(BaseModel):
    flows: list[FlowRead]
    folder_name: str
    description: str

class InitResponse(BaseModel):
    flow_id: str = Field(serialization_alias="flowId")

class BuiltResponse(BaseModel):
    built: bool

class UploadFileResponse(BaseModel):
    flow_id: str = Field(serialization_alias="flowId")
    file_path: Path

class StreamData(BaseModel):
    event: str
    data: dict

    def __str__(self) -> str:
        from langflow.services.database.models.base import orjson_dumps
        return f"event: {self.event}\ndata: {orjson_dumps(self.data, indent_2=False)}\n\n"

class VertexBuildResponse(BaseModel):
    id: str | None = None
    inactivated_vertices: list[str] | None = None
    next_vertices_ids: list[str] | None = None
    top_level_vertices: list[str] | None = None
    valid: bool
    params: Any | None = Field(default_factory=dict)
    data: ResultDataResponse
    timestamp: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def serialize_data(data: ResultDataResponse) -> dict:
        from langflow.serialization.serialization import serialize
        from langflow.serialization.constants import MAX_TEXT_LENGTH, MAX_ITEMS_LENGTH
        return serialize(data, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)

class VerticesBuiltResponse(BaseModel):
    vertices: list[VertexBuildResponse]

class FlowDataRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    viewport: dict | None = None

class CancelFlowResponse(BaseModel):
    success: bool
    message: str

class MCPSettings(BaseModel):
    id: UUID
    mcp_enabled: bool | None = None
    action_name: str | None = None
    action_description: str | None = None
    name: str | None = None
    description: str | None = None

class VerticesOrderResponse(BaseModel):
    ids: list[str]
    run_id: UUID
    vertices_to_run: list[str]
