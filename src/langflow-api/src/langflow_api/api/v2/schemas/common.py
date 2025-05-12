from enum import Enum
from typing import Any, Optional, List, Dict
from datetime import datetime, timezone
import re

from pydantic import BaseModel, Field, field_validator, field_serializer, model_serializer, ConfigDict

from langflow.graph.schema import RunOutputs
from langflow.schema.schema import OutputValue
from langflow.services.tracing.schema import Log

from langflow_api.api.v2.schemas.feature_flags import FeatureFlags

class BuildStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    STARTED = "started"
    IN_PROGRESS = "in_progress"

class TweaksRequest(BaseModel):
    tweaks: dict[str, dict[str, Any]] | None = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str | None = Field(None)
    href: str | None = Field(None)

class ProcessResponse(BaseModel):
    result: Any
    status: str | None = None
    task: TaskResponse | None = None
    session_id: str | None = None
    backend: str | None = None

class RunResponse(BaseModel):
    outputs: list[RunOutputs] | None = []
    session_id: str | None = None

    @model_serializer(mode="plain")
    def serialize(self):
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

class PreloadResponse(BaseModel):
    session_id: str | None = None
    is_clear: bool | None = None

class TaskStatusResponse(BaseModel):
    status: str
    result: Any | None = None

class CustomComponentRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    code: str
    frontend_node: dict | None = None

class CustomComponentResponse(BaseModel):
    data: dict
    type: str

class UpdateCustomComponentRequest(CustomComponentRequest):
    field: str
    field_value: str | int | float | bool | dict | list | None = None
    template: dict
    tool_mode: bool = False

    def get_template(self):
        from langflow.schema import dotdict
        return dotdict(self.template)

class CustomComponentResponseError(BaseModel):
    detail: str
    traceback: str

class ComponentListCreate(BaseModel):
    flows: list[FlowCreate]

class ComponentListRead(BaseModel):
    flows: list[FlowRead]

class ResultDataResponse(BaseModel):
    results: Any | None = Field(default_factory=dict)
    outputs: dict[str, OutputValue] = Field(default_factory=dict)
    logs: dict[str, list[Log]] = Field(default_factory=dict)
    message: Any | None = Field(default_factory=dict)
    artifacts: Any | None = Field(default_factory=dict)
    timedelta: float | None = None
    duration: str | None = None
    used_frozen_result: bool | None = False

    @field_serializer("results")
    @classmethod
    def serialize_results(cls, v):
        from langflow.serialization.serialization import serialize
        from langflow.serialization.constants import MAX_TEXT_LENGTH, MAX_ITEMS_LENGTH
        return serialize(v, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)

    @model_serializer(mode="plain")
    def serialize_model(self) -> dict:
        from langflow.serialization.serialization import serialize
        from langflow.serialization.constants import MAX_TEXT_LENGTH, MAX_ITEMS_LENGTH
        return {
            "results": self.serialize_results(self.results),
            "outputs": serialize(self.outputs, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH),
            "logs": serialize(self.logs, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH),
            "message": serialize(self.message, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH),
            "artifacts": serialize(self.artifacts, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH),
            "timedelta": self.timedelta,
            "duration": self.duration,
            "used_frozen_result": self.used_frozen_result,
        }

class ConfigResponse(BaseModel):
    feature_flags: FeatureFlags
    serialization_max_items_lenght: int
    serialization_max_text_length: int
    frontend_timeout: int
    auto_saving: bool
    auto_saving_interval: int
    health_check_max_retries: int
    max_file_size_upload: int
    webhook_polling_interval: int
    public_flow_cleanup_interval: int
    public_flow_expiration: int
    event_delivery: str

class UpdateTemplateRequest(BaseModel):
    template: dict
