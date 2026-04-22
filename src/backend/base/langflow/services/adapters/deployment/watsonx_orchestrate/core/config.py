"""Config management functions for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_clients.connections.connections_client import ListConfigsResponse
from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
)
from lfx.services.adapters.deployment.exceptions import (
    DeploymentNotFoundError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.deployment.schema import (
    ConfigItem,
    ConfigListItem,
    ConfigListParams,
    ConfigListResult,
    DeploymentConfig,
    IdLike,
)
from lfx.services.adapters.payload import AdapterPayloadMissingError, AdapterPayloadValidationError, PayloadSlot

from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_runtime_credentials
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import extract_langflow_connections_binding
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    raise_as_deployment_error,
    require_single_deployment_id,
    validate_wxo_name,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ibm_watsonx_orchestrate_clients.connections.connections_client import (
        ConnectionsClient,
        GetConnectionResponse,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        WatsonxConfigItemProviderData,
        WatsonxConfigListResultData,
    )
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


async def create_config(
    *,
    clients: WxOClient,
    config: DeploymentConfig,
    user_id: IdLike,
    db: AsyncSession,
    created_app_ids_journal: list[str] | None = None,
) -> str:
    """Create/update a wxO draft key-value connection config plus runtime credentials.

    When ``created_app_ids_journal`` is provided, ``app_id`` is appended
    immediately after provider connection creation succeeds so rollback can
    clean up partially completed creates.
    """
    app_id = validate_wxo_name(config.name)
    env_var_keys = list((config.environment_variables or {}).keys())
    logger.debug("create_config: app_id='%s', env_var_keys=%s", app_id, env_var_keys)

    await asyncio.to_thread(clients.connections.create, payload={"app_id": app_id})
    if created_app_ids_journal is not None:
        created_app_ids_journal.append(app_id)

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
    logger.debug("create_config: completed for app_id='%s'", app_id)

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
    deployment_name: str,
    config: ConfigItem | None,
) -> str:
    validate_config_create_input(config)
    if config is None or config.raw_payload is None:
        return f"{deployment_name}_app_id"

    normalized_config_name = validate_wxo_name(config.raw_payload.name)
    return f"{deployment_name}_{normalized_config_name}_app_id"


def normalize_optional_text(value: str | None) -> str | None:
    """Strip whitespace and return ``None`` for empty/blank strings."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"normalize_optional_text: expected str | None, got {type(value).__name__}: {value!r}"
        raise TypeError(msg)
    normalized = value.strip()
    return normalized or None


def build_config_list_item(
    *,
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
    connection_id: str,
    app_id: str,
    config_type: str | None = None,
    environment: str | None = None,
) -> ConfigListItem:
    """Build a normalized config list item from resolved identifiers."""
    try:
        provider_data = config_item_data_slot.apply(
            {
                "type": config_type,
                "environment": environment,
            }
        )
    except (AdapterPayloadMissingError, AdapterPayloadValidationError) as exc:
        detail = exc.format_first_error() if isinstance(exc, AdapterPayloadValidationError) else str(exc)
        if normalize_optional_text(config_type) == "key_value_creds" and not normalize_optional_text(environment):
            msg = (
                "wxO returned a key_value_creds connection without a required environment: "
                f"connection_id='{connection_id}', app_id='{app_id}'."
            )
        else:
            msg = (
                "wxO returned an invalid config item provider_data payload: "
                f"connection_id='{connection_id}', app_id='{app_id}', detail='{detail}'."
            )
        raise InvalidContentError(message=msg) from None

    return ConfigListItem(
        id=connection_id,
        name=app_id,
        provider_data=provider_data,
    )


def warn_if_expected_ids_missing(
    *,
    deployment_id: str,
    resource_name: str,
    expected_ids: Iterable[object],
    resolved_ids: set[object],
) -> None:
    missing_ids = [resource_id for resource_id in expected_ids if resource_id not in resolved_ids]
    if missing_ids:
        logger.warning(
            "list_configs: deployment '%s' references %s IDs not returned by provider "
            "(possibly stale/deleted between reads): %s",
            deployment_id,
            resource_name,
            missing_ids,
        )


def _should_include_connection(
    connection: ListConfigsResponse,
) -> bool:
    """Return True if the connection is a key-value connection in draft mode, otherwise False."""
    return (
        connection.security_scheme == ConnectionSecurityScheme.KEY_VALUE
        and connection.environment == ConnectionEnvironment.DRAFT
    )


def _build_tenant_scope_config_items(
    *,
    raw_connections: list[ListConfigsResponse] | None,
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
) -> list[ConfigListItem]:
    configs: list[ConfigListItem] = []
    for connection in raw_connections or []:
        if not isinstance(connection, ListConfigsResponse):
            msg = f"wxO list_configs returned an unexpected connection entry type: {type(connection).__name__}."
            raise InvalidContentError(message=msg)
        if not _should_include_connection(connection):
            continue
        configs.append(
            build_config_list_item(
                config_item_data_slot=config_item_data_slot,
                connection_id=connection.connection_id,
                app_id=connection.app_id,
                config_type=connection.security_scheme,
                environment=connection.environment,
            )
        )
    return configs


def _collect_tool_connection_ids(
    *,
    tools: list[dict],
) -> tuple[set[str], set[object]]:
    all_tool_connection_ids: set[str] = set()
    resolved_tool_ids: set[object] = set()
    for tool in tools:
        tool_id = tool.get("id")
        resolved_tool_ids.add(tool_id)
        connections = extract_langflow_connections_binding(tool)
        all_tool_connection_ids.update(connections.values())
    return all_tool_connection_ids, resolved_tool_ids


def _build_deployment_scope_config_items(
    *,
    detailed_connections: list[ListConfigsResponse],
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
) -> tuple[list[ConfigListItem], set[object]]:
    configs: list[ConfigListItem] = []
    resolved_connection_ids: set[object] = set()
    for connection in detailed_connections:
        connection_id = connection.connection_id
        resolved_connection_ids.add(connection_id)

        if not _should_include_connection(connection):
            continue
        configs.append(
            build_config_list_item(
                config_item_data_slot=config_item_data_slot,
                connection_id=connection_id,
                app_id=connection.app_id,
                config_type=connection.security_scheme,
                environment=connection.environment,
            )
        )
    return configs, resolved_connection_ids


async def _fetch_deployment_agent_for_configs(
    *,
    clients: WxOClient,
    agent_id: str,
) -> dict[str, Any]:
    try:
        agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)
    except Exception as exc:  # noqa: BLE001
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.LIST_CONFIGS,
            log_msg="Unexpected error while listing wxO deployment configs",
        )

    if not agent:
        msg = f"Deployment '{agent_id}' not found."
        raise DeploymentNotFoundError(msg)
    if not isinstance(agent, dict):
        msg = f"wxO returned an unexpected deployment payload type for '{agent_id}': {type(agent).__name__}."
        raise InvalidContentError(message=msg)
    return agent


async def _resolve_deployment_scope_configs(
    *,
    clients: WxOClient,
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
    agent_id: str,
    tool_ids: object,
) -> list[ConfigListItem]:
    tools: list[dict]
    try:
        tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, tool_ids)
    except Exception as exc:  # noqa: BLE001
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.LIST_CONFIGS,
            log_msg="Unexpected error while listing wxO tools for config extraction",
        )

    all_tool_connection_ids, resolved_tool_ids = _collect_tool_connection_ids(tools=tools)

    warn_if_expected_ids_missing(
        deployment_id=agent_id,
        resource_name="tool",
        expected_ids=tool_ids,
        resolved_ids=resolved_tool_ids,
    )

    configs: list[ConfigListItem] = []
    # duplication might occur given the list connections api returns
    # two entries per app id, one for draft and one for live
    connection_ids = list(all_tool_connection_ids)
    if connection_ids:
        try:
            detailed_connections = await asyncio.to_thread(clients.connections.get_drafts_by_ids, connection_ids)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST_CONFIGS,
                log_msg="Unexpected error while enriching wxO deployment configs with connection types",
            )
        else:
            configs, resolved_connection_ids = _build_deployment_scope_config_items(
                detailed_connections=detailed_connections,
                config_item_data_slot=config_item_data_slot,
            )
            warn_if_expected_ids_missing(
                deployment_id=agent_id,
                resource_name="connection",
                expected_ids=connection_ids,
                resolved_ids=resolved_connection_ids,
            )

    return configs


async def _list_deployment_scope_configs(
    *,
    clients: WxOClient,
    params: ConfigListParams,
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
    config_list_result_slot: PayloadSlot[WatsonxConfigListResultData],
) -> ConfigListResult:
    agent_id = require_single_deployment_id(params, resource_label="config")
    agent = await _fetch_deployment_agent_for_configs(clients=clients, agent_id=agent_id)

    raw_tool_ids = agent.get("tools", [])
    if raw_tool_ids is None:
        raw_tool_ids = []
    tool_ids = raw_tool_ids

    if not tool_ids:
        return ConfigListResult(
            configs=[],
            provider_result=config_list_result_slot.parse({"deployment_id": agent_id, "tool_ids": []}).model_dump(
                exclude_none=True
            ),
        )

    configs = await _resolve_deployment_scope_configs(
        clients=clients,
        config_item_data_slot=config_item_data_slot,
        agent_id=agent_id,
        tool_ids=tool_ids,
    )

    return ConfigListResult(
        configs=configs,
        provider_result=config_list_result_slot.parse({"deployment_id": agent_id}).model_dump(exclude_none=True),
    )


async def list_configs(
    *,
    clients: WxOClient,
    params: ConfigListParams | None,
    config_item_data_slot: PayloadSlot[WatsonxConfigItemProviderData],
    config_list_result_slot: PayloadSlot[WatsonxConfigListResultData],
) -> ConfigListResult:
    if not params or not params.deployment_ids:
        try:
            raw_connections = await asyncio.to_thread(clients.connections.list)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST_CONFIGS,
                log_msg="Unexpected error while listing wxO tenant configs",
            )

        return ConfigListResult(
            configs=_build_tenant_scope_config_items(
                raw_connections=raw_connections,
                config_item_data_slot=config_item_data_slot,
            ),
            provider_result=config_list_result_slot.parse({}).model_dump(exclude_none=True),
        )

    return await _list_deployment_scope_configs(
        clients=clients,
        params=params,
        config_item_data_slot=config_item_data_slot,
        config_list_result_slot=config_list_result_slot,
    )


async def validate_connection(connections_client: ConnectionsClient, *, app_id: str) -> GetConnectionResponse:
    logger.debug("validate_connection: app_id='%s'", app_id)

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

    logger.debug(
        "validate_connection: passed for app_id='%s', connection_id='%s'",
        app_id,
        getattr(connection, "connection_id", "unknown"),
    )
    return connection
