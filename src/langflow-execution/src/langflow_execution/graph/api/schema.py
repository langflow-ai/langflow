from pydantic import BaseModel

class GraphExecutionRequest(BaseModel):
    input_value: str | None = None

class GraphExecutionResponse(BaseModel):
    output_value: str | None = None
