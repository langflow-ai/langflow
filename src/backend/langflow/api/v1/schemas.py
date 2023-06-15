from typing import Any, Dict, List, Optional, Union
from langflow.database.models.flow import FlowCreate, FlowRead
from pydantic import BaseModel, Field, validator


class GraphData(BaseModel):
    """Data inside the exported flow."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class ExportedFlow(BaseModel):
    """Exported flow from LangFlow."""

    description: str
    name: str
    id: str
    data: GraphData


class PredictRequest(BaseModel):
    """Predict request schema."""

    message: str
    tweaks: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)

    class Config:
        schema_extra = {
            "example": {
                "message": "Hello, how are you?",
                "tweaks": {
                    "dndnode_986363f0-4677-4035-9f38-74b94af5dd78": {
                        "name": "A tool name",
                        "description": "A tool description",
                    },
                    "dndnode_986363f0-4677-4035-9f38-74b94af57378": {
                        "template": "A {template}",
                    },
                },
            }
        }


class PredictResponse(BaseModel):
    """Predict response schema."""

    result: str
    intermediate_steps: str = ""


class ChatMessage(BaseModel):
    """Chat message schema."""

    is_bot: bool = False
    message: Union[str, None] = None
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
