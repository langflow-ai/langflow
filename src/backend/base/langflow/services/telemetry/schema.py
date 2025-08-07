from pydantic import BaseModel, Field


class RunPayload(BaseModel):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class ShutdownPayload(BaseModel):
    time_running: int = Field(serialization_alias="timeRunning")
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class VersionPayload(BaseModel):
    package: str
    version: str
    platform: str
    python: str
    arch: str
    auto_login: bool = Field(serialization_alias="autoLogin")
    cache_type: str = Field(serialization_alias="cacheType")
    backend_only: bool = Field(serialization_alias="backendOnly")
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class PlaygroundPayload(BaseModel):
    playground_seconds: int = Field(serialization_alias="playgroundSeconds")
    playground_component_count: int | None = Field(None, serialization_alias="playgroundComponentCount")
    playground_success: bool = Field(serialization_alias="playgroundSuccess")
    playground_error_message: str = Field("", serialization_alias="playgroundErrorMessage")
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class ComponentPayload(BaseModel):
    component_name: str = Field(serialization_alias="componentName")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(serialization_alias="componentErrorMessage")
    client_type: str | None = Field(default=None, serialization_alias="clientType")
