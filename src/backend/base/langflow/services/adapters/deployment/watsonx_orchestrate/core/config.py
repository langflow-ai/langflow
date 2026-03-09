"""Config management functions for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
)
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.deployment.schema import ConfigItem, DeploymentConfig, IdLike

from langflow.services.adapters.deployment.watsonx_orchestrate.client import (
    get_provider_clients,
    resolve_runtime_credentials,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

if TYPE_CHECKING:
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


async def create_config(
    *,
    config: DeploymentConfig,
    user_id: IdLike,
    db: Any,
    client_cache: dict[str, Any],
) -> str:
    """Create/update a WXO draft key-value connection config plus runtime credentials."""
    clients = await get_provider_clients(
        user_id=user_id,
        db=db,
        client_cache=client_cache,
    )

    app_id = validate_wxo_name(config.name)

    clients.connections.create(payload={"app_id": app_id})

    wxo_config = ConnectionConfiguration(
        app_id=app_id,
        environment=ConnectionEnvironment.DRAFT,
        preference=ConnectionPreference.TEAM,
        security_scheme=ConnectionSecurityScheme.KEY_VALUE,
    )
    clients.connections.create_config(
        app_id=app_id, payload=wxo_config.model_dump(exclude_unset=True, exclude_none=True)
    )

    runtime_credentials = await resolve_runtime_credentials(
        environment_variables=config.environment_variables or {},
        user_id=user_id,
        db=db,
    )

    clients.connections.create_credentials(
        app_id=app_id,
        env=ConnectionEnvironment.DRAFT,
        use_app_credentials=False,
        payload={"runtime_credentials": runtime_credentials.model_dump()},
    )

    return app_id


async def process_config(
    user_id: Any,
    db: Any,
    deployment_name: str,
    config: ConfigItem | None,
    *,
    client_cache: dict[str, Any],
) -> str:
    """Create and bind deployment config using deployment name as app_id."""
    validate_config_create_input(config)

    environment_variables = None
    description = ""

    if config and config.raw_payload:
        environment_variables = config.raw_payload.environment_variables
        description = config.raw_payload.description or ""

    config_payload = DeploymentConfig(
        name=deployment_name,
        description=description,
        environment_variables=environment_variables,
    )
    app_id: str = await create_config(
        config=config_payload,
        user_id=user_id,
        db=db,
        client_cache=client_cache,
    )

    return app_id


def validate_config_create_input(config: ConfigItem | None) -> None:
    if config and config.reference_id is not None:
        msg = (
            "Config reference binding is not supported for deployment creation in "
            "watsonx Orchestrate. Provide raw config payload or omit config."
        )
        raise InvalidDeploymentOperationError(message=msg)


def resolve_create_app_id(
    *,
    prefixed_deployment_name: str,
    config: ConfigItem | None,
) -> str:
    validate_config_create_input(config)
    if config is None or config.raw_payload is None:
        return f"{prefixed_deployment_name}_app_id"

    normalized_config_name = validate_wxo_name(config.raw_payload.name)
    return f"{prefixed_deployment_name}_{normalized_config_name}_app_id"


def assert_create_resources_available(
    *,
    clients: WxOClient,
    deployment_name: str,
    app_id: str,
    snapshot_tool_names: list[str] | None = None,
) -> None:
    """Fail fast when deployment resource names conflict with existing resources."""
    existing_agents = clients.agent.get_draft_by_name(deployment_name)
    if existing_agents:
        msg = f"{ErrorPrefix.CREATE.value}. Deployment '{deployment_name}' already exists."
        raise DeploymentConflictError(message=msg)

    existing_connection = clients.connections.get_draft_by_app_id(app_id=app_id)
    if existing_connection:
        msg = f"{ErrorPrefix.CREATE.value}. Deployment config '{app_id}' already exists."
        raise DeploymentConflictError(message=msg)

    if not snapshot_tool_names:
        return

    seen_tool_names: set[str] = set()
    duplicate_tool_names: set[str] = set()
    for tool_name in snapshot_tool_names:
        if tool_name in seen_tool_names:
            duplicate_tool_names.add(tool_name)
        seen_tool_names.add(tool_name)
    if duplicate_tool_names:
        duplicates = ", ".join(sorted(duplicate_tool_names))
        msg = f"{ErrorPrefix.CREATE.value}. Deployment snapshot name(s) duplicated: {duplicates}."
        raise DeploymentConflictError(message=msg)

    for tool_name in snapshot_tool_names:
        existing_tools = clients.tool.get_draft_by_name(tool_name)
        if existing_tools:
            msg = f"{ErrorPrefix.CREATE.value}. Deployment snapshot '{tool_name}' already exists."
            raise DeploymentConflictError(message=msg)


def validate_connection(connections_client: Any, *, app_id: str) -> Any:
    from ibm_watsonx_orchestrate_core.types.connections import ConnectionEnvironment, ConnectionSecurityScheme

    connection = connections_client.get_draft_by_app_id(app_id=app_id)
    config = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.DRAFT)
    if not connection:
        msg = f"Connection '{app_id}' is missing draft config. Deployments require draft mode."
        raise ValueError(msg)
    if config.security_scheme != ConnectionSecurityScheme.KEY_VALUE:
        msg = f"Connection '{app_id}' must use key-value credentials for Langflow flows."
        raise ValueError(msg)
    runtime_credentials = connections_client.get_credentials(
        app_id=app_id,
        env=ConnectionEnvironment.DRAFT,
        use_app_credentials=False,
    )
    if not runtime_credentials:
        msg = f"Connection '{app_id}' is missing draft runtime credentials."
        raise ValueError(msg)

    return connection
