from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_serializer, model_validator

from langflow.graph.utils import serialize_field
from langflow.schema.schema import OutputValue, StreamURL
from langflow.utils.schemas import ChatOutputResponse, ContainsEnumMeta


class ResultData(BaseModel):
    results: Optional[Any] = Field(default_factory=dict)
    artifacts: Optional[Any] = Field(default_factory=dict)
    outputs: Optional[dict] = Field(default_factory=dict)
    logs: Optional[dict] = Field(default_factory=dict)
    messages: Optional[list[ChatOutputResponse]] = Field(default_factory=list)
    timedelta: Optional[float] = None
    duration: Optional[str] = None
    component_display_name: Optional[str] = None
    component_id: Optional[str] = None
    used_frozen_result: Optional[bool] = False

    @field_serializer("results")
    def serialize_results(self, value):
        if isinstance(value, dict):
            return {key: serialize_field(val) for key, val in value.items()}
        return serialize_field(value)

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
                    values["outputs"].update({OutputValue(message=message, type=message["type"])})
        return values


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    # ChatInput and ChatOutput are the only ones that are
    # power components
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"
    DataOutput = "DataOutput"
    WebhookInput = "Webhook"

    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


CHAT_COMPONENTS = [InterfaceComponentTypes.ChatInput, InterfaceComponentTypes.ChatOutput]
RECORDS_COMPONENTS = [InterfaceComponentTypes.DataOutput]
INPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatInput,
    InterfaceComponentTypes.TextInput,
    InterfaceComponentTypes.WebhookInput,
]
OUTPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatOutput,
    InterfaceComponentTypes.TextOutput,
    InterfaceComponentTypes.DataOutput,
]


class RunOutputs(BaseModel):
    inputs: dict = Field(default_factory=dict)
    outputs: List[Optional[ResultData]] = Field(default_factory=list)
