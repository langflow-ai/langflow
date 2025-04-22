from pydantic import BaseModel, Field, field_serializer


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


class FlowCreatedPayload(BaseModel):
    """Telemetry payload for the `flow_created` event."""

    flow_id: str = Field(serialization_alias="flowId")
    timestamp: int = Field(serialization_alias="timestamp")

    # Optional / helpful fields
    source: str | None = Field(None, serialization_alias="source")
    initial_component_count: int | None = Field(None, serialization_alias="initialComponentCount")
    initial_component_list: list[str] | None = Field(None, serialization_alias="initialComponentList")

    @field_serializer("initial_component_list")
    @classmethod
    def serialize_initial_component_list(cls, value: list[str]) -> str:
        # serialize as a csv string
        if isinstance(value, list):
            return ",".join(value)
        return value


class FlowEditedPayload(BaseModel):
    """Telemetry payload for the `flow_edited` event."""

    flow_id: str = Field(serialization_alias="flowId")
    timestamp: int = Field(serialization_alias="timestamp")
    edit_type: str = Field(serialization_alias="editType")  # add_component | remove_component | update_component
    component_id: str = Field(serialization_alias="componentId")


class FlowRenamedPayload(BaseModel):
    """Telemetry payload for the `flow_renamed` event."""

    flow_id: str = Field(serialization_alias="flowId")
    timestamp: int = Field(serialization_alias="timestamp")
    new_name: str = Field(serialization_alias="newName")
    new_description: str = Field(serialization_alias="newDescription")
