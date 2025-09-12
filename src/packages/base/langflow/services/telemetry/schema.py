from pydantic import BaseModel, Field


class RunPayload(BaseModel):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")


class ShutdownPayload(BaseModel):
    time_running: int = Field(serialization_alias="timeRunning")


class VersionPayload(BaseModel):
    package: str
    version: str
    platform: str
    python: str
    arch: str
    auto_login: bool = Field(serialization_alias="autoLogin")
    cache_type: str = Field(serialization_alias="cacheType")
    backend_only: bool = Field(serialization_alias="backendOnly")
    desktop: bool = False


class PlaygroundPayload(BaseModel):
    playground_seconds: int = Field(serialization_alias="playgroundSeconds")
    playground_component_count: int | None = Field(None, serialization_alias="playgroundComponentCount")
    playground_success: bool = Field(serialization_alias="playgroundSuccess")
    playground_error_message: str = Field("", serialization_alias="playgroundErrorMessage")


class ComponentPayload(BaseModel):
    component_name: str = Field(serialization_alias="componentName")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(serialization_alias="componentErrorMessage")


class ExceptionPayload(BaseModel):
    exception_type: str = Field(serialization_alias="exceptionType")
    exception_message: str = Field(serialization_alias="exceptionMessage")
    exception_context: str = Field(serialization_alias="exceptionContext")  # "lifespan" or "handler"
    stack_trace_hash: str | None = Field(None, serialization_alias="stackTraceHash")  # Hash for grouping
