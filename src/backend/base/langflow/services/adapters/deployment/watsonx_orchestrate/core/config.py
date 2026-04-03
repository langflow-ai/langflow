"""Config management functions for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

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
from langflow.services.adapters.deployment.watsonx_orchestrate.local_dev import (
    is_wxo_local_instance_url,
    wxo_local_use_default_api_v1_layout,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_config(
    *,
    clients: Any,
    config: DeploymentConfig,
    user_id: IdLike,
    db: AsyncSession,
) -> str:
    """Create/update a wxO draft key-value connection config plus runtime credentials."""
    app_id = validate_wxo_name(config.name)
    runtime_credentials = await resolve_runtime_credentials(
        environment_variables=config.environment_variables or {},
        user_id=user_id,
        db=db,
    )

    if wxo_local_use_default_api_v1_layout(clients.instance_url):
        # Developer Edition OpenAPI expects a single CreateConnection body (appid, not app_id).
        await asyncio.to_thread(
            clients.connections.create,
            payload={
                "appid": app_id,
                "connection_type": ConnectionSecurityScheme.KEY_VALUE.value,
                "credentials": {"runtime_credentials": runtime_credentials.model_dump()},
                # Matches ConnectionPreference.TEAM used for SaaS multi-step create below.
                "shared": True,
            },
        )
        return app_id

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
    clients: Any,
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
    deployment_name: str,
    config: ConfigItem | None,
) -> str:
    validate_config_create_input(config)
    if config is None or config.raw_payload is None:
        return f"{deployment_name}_app_id"

    normalized_config_name = validate_wxo_name(config.raw_payload.name)
    return f"{deployment_name}_{normalized_config_name}_app_id"


async def validate_connection(clients: Any, *, app_id: str) -> Any:
    """Validate wxO draft connection; ``clients`` is a :class:`WxOClient` (or test double with ``connections``)."""
    getter = getattr(clients, "get_connection_draft_for_validation", None)
    if getter is not None:
        connection = await asyncio.to_thread(getter, app_id)
    else:
        connection = await asyncio.to_thread(clients.connections.get_draft_by_app_id, app_id=app_id)
    if not connection:
        msg = f"Connection '{app_id}' not found. Ensure the connection exists with a draft configuration."
        raise InvalidContentError(message=msg)

    cc = clients.connections
    instance_url = getattr(clients, "instance_url", "") or ""
    local_loopback = is_wxo_local_instance_url(instance_url)
    config = await asyncio.to_thread(cc.get_config, app_id=app_id, env=ConnectionEnvironment.DRAFT)
    if not config:
        # Developer Edition unified CreateConnection may not expose SaaS-style .../configurations/draft.
        if local_loopback:
            return connection
        msg = f"Connection '{app_id}' is missing draft config. Deployments require draft mode."
        raise InvalidContentError(message=msg)

    if config.security_scheme != ConnectionSecurityScheme.KEY_VALUE:
        msg = f"Connection '{app_id}' must use key-value credentials for Langflow flows."
        raise InvalidContentError(message=msg)

    runtime_credentials = await asyncio.to_thread(
        cc.get_credentials,
        app_id=app_id,
        env=ConnectionEnvironment.DRAFT,
        use_app_credentials=False,
    )

    if not runtime_credentials:
        if local_loopback:
            return connection
        msg = f"Connection '{app_id}' is missing draft runtime credentials."
        raise InvalidContentError(message=msg)

    return connection
