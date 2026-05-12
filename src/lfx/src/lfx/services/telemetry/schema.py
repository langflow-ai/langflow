"""Telemetry payload schemas.

Payloads are emitted as OpenTelemetry span event attributes, so keep fields small.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

MAX_TELEMETRY_EVENT_SIZE = 2048
MAX_TELEMETRY_URL_SIZE = MAX_TELEMETRY_EVENT_SIZE


class BasePayload(BaseModel):
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class RunPayload(BasePayload):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str | None = Field(None, serialization_alias="runErrorMessage")


class ShutdownPayload(BasePayload):
    time_running: int = Field(serialization_alias="timeRunning")


class VersionPayload(BasePayload):
    package: str
    version: str
    platform: str
    python: str
    arch: str


class ComponentPayload(BasePayload):
    component_name: str = Field(serialization_alias="componentName")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(None, serialization_alias="componentErrorMessage")


class ExceptionPayload(BasePayload):
    exception_type: str = Field(serialization_alias="exceptionType")
    exception_message: str = Field(serialization_alias="exceptionMessage")
    exception_context: str = Field(serialization_alias="exceptionContext")
    stack_trace_hash: str | None = Field(None, serialization_alias="stackTraceHash")


class MCPToolPayload(BasePayload):
    """Tracks an MCP tool invocation. Kept small for telemetry event attributes."""

    tool: str
    success: bool
    ms: int = Field(0, serialization_alias="ms")
    error: str | None = None
