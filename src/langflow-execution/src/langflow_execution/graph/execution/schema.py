from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from langflow_execution.schema.schema import InputType


# TODO: This came from SimplifiedAPIRequest class
class FlowExecutionRequest(BaseModel):
    """Request model for executing a flow.

    Attributes:
        input_value (Optional[str]): The input value for the flow execution.
        input_type (Optional[str]): The type of input (default: 'chat').
        output_type (Optional[str]): The type of output expected (default: 'chat').
        output_component (Optional[str]): Specify the output component if multiple are present.
        tweaks (Optional[dict]): Optional tweaks or overrides for the flow execution.
        session_id (Optional[str]): Optional session identifier for the flow run.
    """

    input_value: str | None = Field(default=None, description="The input value")
    input_type: str | None = Field(default="chat", description="The input type")
    output_type: str | None = Field(default="chat", description="The output type")
    output_component: str | None = Field(
        default="",
        description="If there are multiple output components, you can specify the component to get the output from.",
    )
    tweaks: dict | None = Field(default=None, description="The tweaks")
    session_id: str | None = Field(default=None, description="The session id")


# TODO: necessary?
class InputValueRequest(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    session: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )

    # add an example
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "components": ["components_id", "Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"components": ["Component Name"], "input_value": "input_value"},
                {"input_value": "input_value"},
                {
                    "components": ["Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"input_value": "input_value", "session": "session_id"},
                {"type": "chat", "input_value": "input_value"},
                {"type": "json", "input_value": '{"key": "value"}'},
            ]
        },
        extra="forbid",
    )


class Flow(BaseModel):
    """The flow to execute.

    Attributes:
        id (str): The unique identifier of the flow.
        name (str): The name of the flow.
        user_id (str): The unique identifier of the user.
        data: (dict): The data of the flow.
          Tweaks should already be applied to the data.
    """

    id: str
    name: str
    user_id: UUID | None = Field(default=None)
    data: dict
