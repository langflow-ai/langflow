import json
from typing import Any

from pydantic import BaseModel, Field


class BasePayload(BaseModel):
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class RunPayload(BasePayload):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")


class ShutdownPayload(BasePayload):
    time_running: int = Field(serialization_alias="timeRunning")


class VersionPayload(BasePayload):
    package: str
    version: str
    platform: str
    python: str
    arch: str
    auto_login: bool = Field(serialization_alias="autoLogin")
    cache_type: str = Field(serialization_alias="cacheType")
    backend_only: bool = Field(serialization_alias="backendOnly")


class PlaygroundPayload(BasePayload):
    playground_seconds: int = Field(serialization_alias="playgroundSeconds")
    playground_component_count: int | None = Field(None, serialization_alias="playgroundComponentCount")
    playground_success: bool = Field(serialization_alias="playgroundSuccess")
    playground_error_message: str = Field("", serialization_alias="playgroundErrorMessage")


class ComponentPayload(BasePayload):
    component_name: str = Field(serialization_alias="componentName")
    component_id: str = Field(serialization_alias="componentId")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(None, serialization_alias="componentErrorMessage")
    component_run_id: str | None = Field(None, serialization_alias="componentRunId")


class ComponentInputsPayload(BasePayload):
    """Separate payload for component input values, joined via component_run_id."""

    component_run_id: str = Field(serialization_alias="componentRunId")
    component_id: str = Field(serialization_alias="componentId")
    component_name: str = Field(serialization_alias="componentName")
    component_inputs: str = Field(serialization_alias="componentInputs")
    chunk_index: int | None = Field(None, serialization_alias="chunkIndex")
    total_chunks: int | None = Field(None, serialization_alias="totalChunks")


class ExceptionPayload(BasePayload):
    exception_type: str = Field(serialization_alias="exceptionType")
    exception_message: str = Field(serialization_alias="exceptionMessage")
    exception_context: str = Field(serialization_alias="exceptionContext")  # "lifespan" or "handler"
    stack_trace_hash: str | None = Field(None, serialization_alias="stackTraceHash")  # Hash for grouping


MAX_INPUTS_JSON_LENGTH = 1500


def serialize_input_values(inputs_dict: dict[str, Any] | None) -> str | None:
    """Serialize component input values to JSON string for query param."""
    if not inputs_dict:
        return None
    try:
        json_str = json.dumps(inputs_dict, separators=(",", ":"))
        # Truncate if too large for URL query param
        return None if len(json_str) > MAX_INPUTS_JSON_LENGTH else json_str
    except (TypeError, ValueError):
        return None
