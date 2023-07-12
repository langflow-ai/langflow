from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from langflow.database.models.flow import FlowCreate, FlowRead
from pydantic import BaseModel, Field, validator
import json


class BuildStatus(Enum):
    """Status of the build."""

    SUCCESS = "success"
    FAILURE = "failure"
    STARTED = "started"
    IN_PROGRESS = "in_progress"


class GraphData(BaseModel):
    """Data inside the exported flow."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class ExportedFlow(BaseModel):
    """Exported flow from Langflow."""

    description: str
    name: str
    id: str
    data: GraphData


class InputRequest(BaseModel):
    input: dict


class TweaksRequest(BaseModel):
    tweaks: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)


class UpdateTemplateRequest(BaseModel):
    template: dict


class ProcessResponse(BaseModel):
    """Process response schema."""

    result: dict


class ChatMessage(BaseModel):
    """Chat message schema."""

    is_bot: bool = False
    message: Union[str, None, dict] = None
    type: str = "human"


class ChatResponse(ChatMessage):
    """Chat response schema."""

    intermediate_steps: str
    type: str
    is_bot: bool = True
    files: list = []

    @validator("type")
    def validate_message_type(cls, v):
        if v not in ["start", "stream", "end", "error", "info", "file"]:
            raise ValueError("type must be start, stream, end, error, info, or file")
        return v


class FileResponse(ChatMessage):
    """File response schema."""

    data: Any
    data_type: str
    type: str = "file"
    is_bot: bool = True

    @validator("data_type")
    def validate_data_type(cls, v):
        if v not in ["image", "csv"]:
            raise ValueError("data_type must be image or csv")
        return v


class FlowListCreate(BaseModel):
    flows: List[FlowCreate]


class FlowListRead(BaseModel):
    flows: List[FlowRead]


class InitResponse(BaseModel):
    flowId: str


class BuiltResponse(BaseModel):
    built: bool


class UploadFileResponse(BaseModel):
    """Upload file response schema."""

    flowId: str
    file_path: Path


class StreamData(BaseModel):
    event: str
    data: dict

    def __str__(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"
