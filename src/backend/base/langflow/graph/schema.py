from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_serializer, model_validator

from langflow.graph.utils import serialize_field
from langflow.schema.schema import Log, StreamURL
from langflow.utils.schemas import ChatOutputResponse, ContainsEnumMeta


class ResultData(BaseModel):
    results: Optional[Any] = Field(default_factory=dict)
    artifacts: Optional[Any] = Field(default_factory=dict)
    logs: Optional[List[dict]] = Field(default_factory=list)
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
        if not values.get("logs") and values.get("artifacts"):
            # Build the log from the artifacts
            message = values["artifacts"]

            # ! Temporary fix
            if not isinstance(message, dict):
                message = {"message": message}

            if "stream_url" in message and "type" in message:
                stream_url = StreamURL(location=message["stream_url"])
                values["logs"] = [Log(message=stream_url, type=message["type"])]
            elif "type" in message:
                values["logs"] = [Log(message=message, type=message["type"])]
        return values


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    # ChatInput and ChatOutput are the only ones that are
    # power components
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"
    RecordsOutput = "RecordsOutput"

    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


CHAT_COMPONENTS = [InterfaceComponentTypes.ChatInput, InterfaceComponentTypes.ChatOutput]
RECORDS_COMPONENTS = [InterfaceComponentTypes.RecordsOutput]
INPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatInput,
    InterfaceComponentTypes.TextInput,
]
OUTPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatOutput,
    InterfaceComponentTypes.TextOutput,
]


class RunOutputs(BaseModel):
    inputs: dict = Field(default_factory=dict)
    outputs: List[Optional[ResultData]] = Field(default_factory=list)
