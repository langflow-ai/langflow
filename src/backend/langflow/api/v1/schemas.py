from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from langflow.services.database.models.api_key.api_key import ApiKeyRead
from langflow.services.database.models.flow import FlowCreate, FlowRead
from langflow.services.database.models.user import UserRead
from langflow.services.database.models.base import orjson_dumps

from pydantic import BaseModel, Field, validator


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


class TaskResponse(BaseModel):
    """Task response schema."""

    id: Optional[str] = Field(None)
    href: Optional[str] = Field(None)


class ProcessResponse(BaseModel):
    """Process response schema."""

    result: Any
    task: Optional[TaskResponse] = None
    session_id: Optional[str] = None
    backend: Optional[str] = None


# TaskStatusResponse(
#         status=task.status, result=task.result if task.ready() else None
#     )
class TaskStatusResponse(BaseModel):
    """Task status response schema."""

    status: str
    result: Optional[Any] = None


class ChatMessage(BaseModel):
    """Chat message schema."""

    is_bot: bool = False
    message: Union[str, None, dict] = None
    chatKey: Optional[str] = None
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


class PromptResponse(ChatMessage):
    """Prompt response schema."""

    prompt: str
    type: str = "prompt"
    is_bot: bool = True


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
        return (
            f"event: {self.event}\ndata: {orjson_dumps(self.data, indent_2=False)}\n\n"
        )


class CustomComponentCode(BaseModel):
    code: str


class CustomComponentResponseError(BaseModel):
    detail: str
    traceback: str


class ComponentListCreate(BaseModel):
    flows: List[FlowCreate]


class ComponentListRead(BaseModel):
    flows: List[FlowRead]


class UsersResponse(BaseModel):
    total_count: int
    users: List[UserRead]


class ApiKeyResponse(BaseModel):
    id: str
    api_key: str
    name: str
    created_at: str
    last_used_at: str


class ApiKeysResponse(BaseModel):
    total_count: int
    user_id: UUID
    api_keys: List[ApiKeyRead]


class CreateApiKeyRequest(BaseModel):
    name: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
