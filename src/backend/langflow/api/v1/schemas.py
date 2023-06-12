from typing import Any, Dict, List, Union

from pydantic import BaseModel, validator


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
    exported_flow: ExportedFlow


class PredictResponse(BaseModel):
    """Predict response schema."""

    result: str


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
