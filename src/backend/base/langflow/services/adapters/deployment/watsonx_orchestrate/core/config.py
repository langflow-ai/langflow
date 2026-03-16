"""Config management functions for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
)
from lfx.services.adapters.deployment.exceptions import (
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.deployment.schema import ConfigItem, DeploymentConfig, IdLike

from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_runtime_credentials
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

if TYPE_CHECKING:
    from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient, GetConnectionResponse
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


async def create_config(
    *,
    clients: WxOClient,
    config: DeploymentConfig,
    user_id: IdLike,
    db: AsyncSession,
) -> str:
    """Create/update a wxO draft key-value connection config plus runtime credentials."""
    app_id = validate_wxo_name(config.name)

    await asyncio.to_thread(clients.connections.create, payload={"app_id": app_id})

    wxo_config = ConnectionConfiguration(
        app_id=app_id,
        environment=ConnectionEnvironment.DRAFT,
        preference=ConnectionPreference.TEAM,
        security_scheme=ConnectionSecurityScheme.KEY_VALUE,
    )
    await asyncio.to_thread(
        clients.connections.create_config,
        app_id=app_id,
        payload=wxo_config.model_dump(exclude_unset=True, exclude_none=True),
    )

    runtime_credentials = await resolve_runtime_credentials(
        environment_variables=config.environment_variables or {},
        user_id=user_id,
        db=db,
    )

    await asyncio.to_thread(
        clients.connections.create_credentials,
        app_id=app_id,
        env=ConnectionEnvironment.DRAFT,
        use_app_credentials=False,
        payload={"runtime_credentials": runtime_credentials.model_dump()},
    )

    return app_id


async def process_config(
    user_id: IdLike,
    db: AsyncSession,
    deployment_name: str,
    config: ConfigItem | None,
    *,
    clients: WxOClient,
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
        clients=clients,
        config=config_payload,
        user_id=user_id,
        db=db,
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


async def validate_connection(connections_client: ConnectionsClient, *, app_id: str) -> GetConnectionResponse:
    connection = await asyncio.to_thread(connections_client.get_draft_by_app_id, app_id=app_id)
    if not connection:
        msg = f"Connection '{app_id}' not found. Ensure the connection exists with a draft configuration."
        raise InvalidContentError(message=msg)

    config = await asyncio.to_thread(connections_client.get_config, app_id=app_id, env=ConnectionEnvironment.DRAFT)
    if not config:
        msg = f"Connection '{app_id}' is missing draft config. Deployments require draft mode."
        raise InvalidContentError(message=msg)

    if config.security_scheme != ConnectionSecurityScheme.KEY_VALUE:
        msg = f"Connection '{app_id}' must use key-value credentials for Langflow flows."
        raise InvalidContentError(message=msg)

    runtime_credentials = await asyncio.to_thread(
        connections_client.get_credentials,
        app_id=app_id,
        env=ConnectionEnvironment.DRAFT,
        use_app_credentials=False,
    )

    if not runtime_credentials:
        msg = f"Connection '{app_id}' is missing draft runtime credentials."
        raise InvalidContentError(message=msg)

    return connection
