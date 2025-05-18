from pydantic import BaseModel, Field
from typing import Optional

class FlowExecutionRequest(BaseModel):
    """
    Request model for executing a flow.

    Attributes:
        input_value (Optional[str]): The input value for the flow execution.
        input_type (Optional[str]): The type of input (default: 'chat').
        output_type (Optional[str]): The type of output expected (default: 'chat').
        output_component (Optional[str]): Specify the output component if multiple are present.
        tweaks (Optional[dict]): Optional tweaks or overrides for the flow execution.
        session_id (Optional[str]): Optional session identifier for the flow run.
    """
    input_value: Optional[str] = Field(default=None, description="The input value")
    input_type: Optional[str] = Field(default="chat", description="The input type")
    output_type: Optional[str] = Field(default="chat", description="The output type")
    output_component: Optional[str] = Field(
        default="",
        description="If there are multiple output components, you can specify the component to get the output from.",
    )
    tweaks: Optional[dict] = Field(default=None, description="The tweaks")
    session_id: Optional[str] = Field(default=None, description="The session id")

class Flow(BaseModel):
    """
    The flow to execute.

    Attributes:
        id (str): The unique identifier of the flow.
        data: (dict): The data of the flow.
    """
    id: str
    data: dict

    
