from datetime import datetime
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class OpenAIResponsesRequest(BaseModel):
    """OpenAI-compatible responses request with flow_id as model parameter."""
    model: str = Field(..., description="The flow ID to execute (used instead of OpenAI model)")
    input: str = Field(..., description="The input text to process")
    stream: bool = Field(default=False, description="Whether to stream the response")
    background: bool = Field(default=False, description="Whether to process in background")
    tools: Optional[List[Any]] = Field(default=None, description="Tools are not supported yet")


class OpenAIResponsesResponse(BaseModel):
    """OpenAI-compatible responses response."""
    id: str
    object: Literal["response"] = "response"
    created: int
    model: str
    output: str
    status: Literal["completed", "in_progress", "failed"] = "completed"


class OpenAIResponsesStreamChunk(BaseModel):
    """OpenAI-compatible responses stream chunk."""
    id: str
    object: Literal["response.chunk"] = "response.chunk"
    created: int
    model: str
    delta: dict
    status: Optional[Literal["completed", "in_progress", "failed"]] = None


class OpenAIErrorResponse(BaseModel):
    error: dict = Field(..., description="Error details")


def create_openai_error(message: str, type_: str = "invalid_request_error", code: Optional[str] = None) -> dict:
    """Create an OpenAI-compatible error response."""
    error_data = {
        "message": message,
        "type": type_,
    }
    if code:
        error_data["code"] = code
    
    return {"error": error_data}