from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any
from uuid import UUID
from datetime import datetime, timezone

from langflow.services.database.models.flow import FlowCreate, FlowRead
from langflow_api.api.v2.schemas.common import ResultDataResponse


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
