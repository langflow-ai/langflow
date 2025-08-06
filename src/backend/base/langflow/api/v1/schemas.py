from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_serializer,
    field_validator,
    model_serializer,
)

from langflow.graph.schema import RunOutputs
from langflow.schema.dotdict import dotdict
from langflow.schema.graph import Tweaks
from langflow.schema.schema import InputType, OutputType, OutputValue
from langflow.serialization.serialization import get_max_items_length, get_max_text_length, serialize
from langflow.services.database.models.api_key.model import ApiKeyRead
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow.model import FlowCreate, FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.settings.base import Settings
from langflow.services.settings.feature_flags import FEATURE_FLAGS, FeatureFlags
from langflow.services.tracing.schema import Log


class BuildStatus(Enum):
    """Status of the build."""

    SUCCESS = "success"
    FAILURE = "failure"
    STARTED = "started"
    IN_PROGRESS = "in_progress"


class TweaksRequest(BaseModel):
    tweaks: dict[str, dict[str, Any]] | None = Field(default_factory=dict)


class UpdateTemplateRequest(BaseModel):
    template: dict


class TaskResponse(BaseModel):
    """Task response schema."""

    id: str | None = Field(None)
    href: str | None = Field(None)


class ProcessResponse(BaseModel):
    """Process response schema."""

    result: Any
    status: str | None = None
    task: TaskResponse | None = None
    session_id: str | None = None
    backend: str | None = None


class RunResponse(BaseModel):
    """Run response schema."""

    outputs: list[RunOutputs] | None = []
    session_id: str | None = None

    @model_serializer(mode="plain")
    def serialize(self):
        # Serialize all the outputs if they are base models
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
    """Preload response schema."""

    session_id: str | None = None
    is_clear: bool | None = None


class TaskStatusResponse(BaseModel):
    """Task status response schema."""

    status: str
    result: Any | None = None


class ChatMessage(BaseModel):
    """Chat message schema."""

    is_bot: bool = False
    message: str | None | dict = None
    chat_key: str | None = Field(None, serialization_alias="chatKey")
    type: str = "human"


class ChatResponse(ChatMessage):
    """Chat response schema."""

    intermediate_steps: str

    type: str
    is_bot: bool = True
    files: list = []

    @field_validator("type")
    @classmethod
    def validate_message_type(cls, v):
        if v not in {"start", "stream", "end", "error", "info", "file"}:
            msg = "type must be start, stream, end, error, info, or file"
            raise ValueError(msg)
        return v


class PromptResponse(ChatMessage):
    """Prompt response schema."""

    prompt: str
    type: str = "prompt"
    is_bot: bool = True


class FileResponse(ChatMessage):
    """File response schema."""

    data: Any = None
    data_type: str
    type: str = "file"
    is_bot: bool = True

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v not in {"image", "csv"}:
            msg = "data_type must be image or csv"
            raise ValueError(msg)
        return v


class FlowListCreate(BaseModel):
    flows: list[FlowCreate]


class FlowListIds(BaseModel):
    flow_ids: list[str]


class FlowListRead(BaseModel):
    flows: list[FlowRead]


class FlowListReadWithFolderName(BaseModel):
    flows: list[FlowRead]
    folder_name: str
    description: str


class InitResponse(BaseModel):
    flow_id: str = Field(serialization_alias="flowId")


class BuiltResponse(BaseModel):
    built: bool


class UploadFileResponse(BaseModel):
    """Upload file response schema."""

    flow_id: str = Field(serialization_alias="flowId")
    file_path: Path


class StreamData(BaseModel):
    event: str
    data: dict

    def __str__(self) -> str:
        return f"event: {self.event}\ndata: {orjson_dumps(self.data, indent_2=False)}\n\n"


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
        return dotdict(self.template)


class CustomComponentResponseError(BaseModel):
    detail: str
    traceback: str


class ComponentListCreate(BaseModel):
    flows: list[FlowCreate]


class ComponentListRead(BaseModel):
    flows: list[FlowRead]


class UsersResponse(BaseModel):
    total_count: int
    users: list[UserRead]


class ApiKeyResponse(BaseModel):
    id: str
    api_key: str
    name: str
    created_at: str
    last_used_at: str


class ApiKeysResponse(BaseModel):
    total_count: int
    user_id: UUID
    api_keys: list[ApiKeyRead]


class CreateApiKeyRequest(BaseModel):
    name: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class ApiKeyCreateRequest(BaseModel):
    api_key: str


class VerticesOrderResponse(BaseModel):
    ids: list[str]
    run_id: UUID
    vertices_to_run: list[str]


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
        """Serializes the results value with custom handling for special types and applies truncation limits.

        Returns:
            The serialized representation of the input value, truncated according to configured
            maximum text length and item count.
        """
        return serialize(v, max_length=get_max_text_length(), max_items=get_max_items_length())

    @model_serializer(mode="plain")
    def serialize_model(self) -> dict:
        """Serialize the entire model into a dictionary with truncation applied to large fields.

        Returns:
            dict: A dictionary representation of the model with serialized and truncated
            results, outputs, logs, message, and artifacts.
        """
        return {
            "results": self.serialize_results(self.results),
            "outputs": serialize(self.outputs, max_length=get_max_text_length(), max_items=get_max_items_length()),
            "logs": serialize(self.logs, max_length=get_max_text_length(), max_items=get_max_items_length()),
            "message": serialize(self.message, max_length=get_max_text_length(), max_items=get_max_items_length()),
            "artifacts": serialize(self.artifacts, max_length=get_max_text_length(), max_items=get_max_items_length()),
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
    """JSON string of the params."""
    data: ResultDataResponse
    """Mapping of vertex ids to result dict containing the param name and result value."""
    timestamp: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp of the build."""

    @field_serializer("data")
    def serialize_data(self, data: ResultDataResponse) -> dict:
        """Serialize a ResultDataResponse object into a dictionary with enforced maximum text and item lengths.

        Parameters:
            data (ResultDataResponse): The data object to serialize.

        Returns:
            dict: The serialized representation of the data with truncation applied.
        """
        # return serialize(data, max_length=get_max_text_length())  TODO: Safe?
        return serialize(data, max_length=get_max_text_length(), max_items=get_max_items_length())


class VerticesBuiltResponse(BaseModel):
    vertices: list[VertexBuildResponse]


class InputValueRequest(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    session: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )

    # add an example
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "components": ["components_id", "Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"components": ["Component Name"], "input_value": "input_value"},
                {"input_value": "input_value"},
                {
                    "components": ["Component Name"],
                    "input_value": "input_value",
                    "session": "session_id",
                },
                {"input_value": "input_value", "session": "session_id"},
                {"type": "chat", "input_value": "input_value"},
                {"type": "json", "input_value": '{"key": "value"}'},
            ]
        },
        extra="forbid",
    )


class SimplifiedAPIRequest(BaseModel):
    input_value: str | None = Field(default=None, description="The input value")
    input_type: InputType | None = Field(default="chat", description="The input type")
    output_type: OutputType | None = Field(default="chat", description="The output type")
    output_component: str | None = Field(
        default="",
        description="If there are multiple output components, you can specify the component to get the output from.",
    )
    tweaks: Tweaks | None = Field(default=None, description="The tweaks")
    session_id: str | None = Field(default=None, description="The session id")


# (alias) type ReactFlowJsonObject<NodeData = any, EdgeData = any> = {
#     nodes: Node<NodeData>[];
#     edges: Edge<EdgeData>[];
#     viewport: Viewport;
# }
# import ReactFlowJsonObject
class FlowDataRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    viewport: dict | None = None


class ConfigResponse(BaseModel):
    feature_flags: FeatureFlags
    serialization_max_items_length: int
    serialization_max_text_length: int
    frontend_timeout: int
    auto_saving: bool
    auto_saving_interval: int
    health_check_max_retries: int
    max_file_size_upload: int
    webhook_polling_interval: int
    public_flow_cleanup_interval: int
    public_flow_expiration: int
    event_delivery: Literal["polling", "streaming", "direct"]
    package_manager: bool

    @classmethod
    def from_settings(cls, settings: Settings) -> "ConfigResponse":
        """Create a ConfigResponse instance using values from a Settings object and global feature flags.

        Parameters:
            settings (Settings): The Settings object containing configuration values.

        Returns:
            ConfigResponse: An instance populated with configuration and feature flag values.
        """
        return cls(
            feature_flags=FEATURE_FLAGS,
            serialization_max_items_length=settings.max_items_length,
            serialization_max_text_length=settings.max_text_length,
            frontend_timeout=settings.frontend_timeout,
            auto_saving=settings.auto_saving,
            auto_saving_interval=settings.auto_saving_interval,
            health_check_max_retries=settings.health_check_max_retries,
            max_file_size_upload=settings.max_file_size_upload,
            webhook_polling_interval=settings.webhook_polling_interval,
            public_flow_cleanup_interval=settings.public_flow_cleanup_interval,
            public_flow_expiration=settings.public_flow_expiration,
            event_delivery=settings.event_delivery,
            package_manager=settings.package_manager,
        )


class CancelFlowResponse(BaseModel):
    """Response model for flow build cancellation."""

    success: bool
    message: str


class AuthSettings(BaseModel):
    """Model representing authentication settings for MCP."""

    auth_type: Literal["none", "apikey", "basic", "bearer", "iam", "oauth"] = "none"
    api_key: SecretStr | None = None
    username: str | None = None
    password: SecretStr | None = None
    bearer_token: SecretStr | None = None
    iam_endpoint: str | None = None
    oauth_host: str | None = None
    oauth_port: str | None = None
    oauth_server_url: str | None = None
    oauth_callback_path: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_auth_url: str | None = None
    oauth_token_url: str | None = None
    oauth_mcp_scope: str | None = None
    oauth_provider_scope: str | None = None


class MCPSettings(BaseModel):
    """Model representing MCP settings for a flow."""

    id: UUID
    mcp_enabled: bool | None = None
    action_name: str | None = None
    action_description: str | None = None
    name: str | None = None
    description: str | None = None


class MCPProjectUpdateRequest(BaseModel):
    """Request model for updating MCP project settings including auth."""

    settings: list[MCPSettings]
    auth_settings: AuthSettings | None = None


class MCPProjectResponse(BaseModel):
    """Response model for MCP project tools with auth settings."""

    tools: list[MCPSettings]
    auth_settings: AuthSettings | None = None


class MCPInstallRequest(BaseModel):
    client: str
