from pydantic import BaseModel, Field


class BasePayload(BaseModel):
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class RunPayload(BasePayload):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")
    run_id: str | None = Field(None, serialization_alias="runId")


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
    playground_run_id: str | None = Field(None, serialization_alias="playgroundRunId")


class ComponentPayload(BasePayload):
    component_name: str = Field(serialization_alias="componentName")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(None, serialization_alias="componentErrorMessage")
    component_run_id: str | None = Field(None, serialization_alias="componentRunId")


class ExceptionPayload(BasePayload):
    exception_type: str = Field(serialization_alias="exceptionType")
    exception_message: str = Field(serialization_alias="exceptionMessage")
    exception_context: str = Field(serialization_alias="exceptionContext")  # "lifespan" or "handler"
    stack_trace_hash: str | None = Field(None, serialization_alias="stackTraceHash")  # Hash for grouping


class ComponentIndexPayload(BasePayload):
    index_source: str = Field(serialization_alias="indexSource")  # "builtin", "cache", or "dynamic"
    num_modules: int = Field(serialization_alias="numModules")
    num_components: int = Field(serialization_alias="numComponents")
    dev_mode: bool = Field(serialization_alias="devMode")
    filtered_modules: str | None = Field(None, serialization_alias="filteredModules")  # CSV if filtering
    load_time_ms: int = Field(serialization_alias="loadTimeMs")
