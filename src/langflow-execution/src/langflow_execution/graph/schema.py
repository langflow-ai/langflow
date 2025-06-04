from enum import Enum
from typing import Any, Literal

from langflow.schema.schema import OutputValue, StreamURL
from langflow.serialization import serialize
from langflow.utils.schemas import ChatOutputResponse, ContainsEnumMeta
from pydantic import BaseModel, Field, field_serializer, model_serializer, model_validator

# TODO: find where this should live
InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


class ResultData(BaseModel):
    results: Any | None = Field(default_factory=dict)
    artifacts: Any | None = Field(default_factory=dict)
    outputs: dict | None = Field(default_factory=dict)
    logs: dict | None = Field(default_factory=dict)
    messages: list[ChatOutputResponse] | None = Field(default_factory=list)
    timedelta: float | None = None
    duration: str | None = None
    component_display_name: str | None = None
    component_id: str | None = None
    used_frozen_result: bool | None = False

    @field_serializer("results")
    def serialize_results(self, value):
        if isinstance(value, dict):
            return {key: serialize(val) for key, val in value.items()}
        return serialize(value)

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values):
        if not values.get("outputs") and values.get("artifacts"):
            # Build the log from the artifacts

            for key in values["artifacts"]:
                message = values["artifacts"][key]

                # ! Temporary fix
                if message is None:
                    continue

                if "stream_url" in message and "type" in message:
                    stream_url = StreamURL(location=message["stream_url"])
                    values["outputs"].update({key: OutputValue(message=stream_url, type=message["type"])})
                elif "type" in message:
                    values["outputs"].update({key: OutputValue(message=message, type=message["type"])})
        return values


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"
    DataOutput = "DataOutput"
    WebhookInput = "Webhook"


CHAT_COMPONENTS = [InterfaceComponentTypes.ChatInput, InterfaceComponentTypes.ChatOutput]
RECORDS_COMPONENTS = [InterfaceComponentTypes.DataOutput]
INPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatInput,
    InterfaceComponentTypes.WebhookInput,
    InterfaceComponentTypes.TextInput,
]
OUTPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatOutput,
    InterfaceComponentTypes.DataOutput,
    InterfaceComponentTypes.TextOutput,
]


class RunOutputs(BaseModel):
    inputs: dict = Field(default_factory=dict)
    outputs: list[ResultData | None] = Field(default_factory=list)


class RunResponse(BaseModel):
    """Run response schema."""

    outputs: list[RunOutputs] | None = []
    session_id: str | None = None

    @model_serializer(mode="plain")
    def serialize(self):
        # Serialize all the outputs if they are base models
        serialized = {"session_id": self.session_id, "outputs": []}
        if self.outputs:
            serialized_outputs = []
            for output in self.outputs:
                if isinstance(output, BaseModel) and not isinstance(output, RunOutputs):
                    serialized_outputs.append(output.model_dump(exclude_none=True))
                else:
                    serialized_outputs.append(output)
            serialized["outputs"] = serialized_outputs
        return serialized


class InputValue(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )
