from datetime import datetime, timezone
from typing import Any

from langflow.schema.schema import OutputValue
from langflow.services.tracing.schema import Log
from pydantic import BaseModel, Field, field_serializer, model_serializer


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
        from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
        from langflow.serialization.serialization import serialize

        return serialize(v, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)

    @model_serializer(mode="plain")
    def serialize_model(self) -> dict:
        from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
        from langflow.serialization.serialization import serialize

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


class VertexBuildResponse(BaseModel):
    id: str | None = None
    inactivated_vertices: list[str] | None = None
    next_vertices_ids: list[str] | None = None
    top_level_vertices: list[str] | None = None
    valid: bool
    params: Any | None = Field(default_factory=dict)
    data: ResultDataResponse
    timestamp: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def serialize_data(data: ResultDataResponse) -> dict:
        from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
        from langflow.serialization.serialization import serialize

        return serialize(data, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)


class VerticesOrderResponse(BaseModel):
    ids: list[str]
    run_id: str
    vertices_to_run: list[str]
