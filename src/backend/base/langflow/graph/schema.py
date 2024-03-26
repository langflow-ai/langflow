from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_serializer

from langflow.graph.utils import serialize_field
from langflow.utils.schemas import ChatOutputResponse, ContainsEnumMeta


class ResultData(BaseModel):
    results: Optional[Any] = Field(default_factory=dict)
    artifacts: Optional[Any] = Field(default_factory=dict)
    messages: Optional[list[ChatOutputResponse]] = Field(default_factory=list)
    timedelta: Optional[float] = None
    duration: Optional[str] = None
    component_display_name: Optional[str] = None
    component_id: Optional[str] = None

    @field_serializer("results")
    def serialize_results(self, value):
        if isinstance(value, dict):
            return {key: serialize_field(val) for key, val in value.items()}
        return serialize_field(value)


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    # ChatInput and ChatOutput are the only ones that are
    # power components
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"

    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


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
