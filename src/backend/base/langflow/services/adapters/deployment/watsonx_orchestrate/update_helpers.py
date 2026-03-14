"""Helpers used to flatten wxO deployment update control flow."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY,
    ErrorPrefix,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import (
    create_config as default_create_config,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import (
    validate_connection as default_validate_connection,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create as default_retry_create,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    rollback_update_resources as default_rollback_update_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    create_and_upload_wxo_flow_tools as default_create_and_upload_wxo_flow_tools,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    update_existing_tool_connection_bindings as default_update_existing_tool_connection_bindings,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    extract_agent_tool_ids,
    extract_error_detail,
    normalize_and_dedupe_ids,
    validate_wxo_name,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentDataUpdate,
        BaseFlowArtifact,
        ConfigDeploymentBindingUpdate,
        IdLike,
        SnapshotDeploymentBindingUpdate,
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SnapshotUpdateOps:
    add_raw_payloads: list[BaseFlowArtifact]
    remove_ids: list[str]
    add_ids: list[str]

    @property
    def has_snapshot_adds(self) -> bool:
        return bool(self.add_ids or self.add_raw_payloads)


def build_update_payload_from_spec(spec: BaseDeploymentDataUpdate | None) -> dict[str, Any]:
    """Build agent update payload from deployment spec updates."""
    update_payload: dict[str, Any] = {}
    if not spec:
        return update_payload

    spec_updates = spec.model_dump(exclude_unset=True)
    if "name" in spec_updates:
        update_payload.update(
            {
                "name": validate_wxo_name(spec_updates["name"]),
                "display_name": spec_updates["name"],
            }
        )
    if "description" in spec_updates:
        update_payload["description"] = spec_updates["description"]
    return update_payload


def extract_snapshot_ops(snapshot_update: SnapshotDeploymentBindingUpdate | None) -> SnapshotUpdateOps:
    """Normalize add/remove snapshot tool ids and raw payloads."""
    if not snapshot_update:
        return SnapshotUpdateOps(add_raw_payloads=[], remove_ids=[], add_ids=[])

    return SnapshotUpdateOps(
        add_raw_payloads=snapshot_update.add_raw_payloads or [],
        remove_ids=normalize_and_dedupe_ids(snapshot_update.remove_ids, field_name="snapshot_id"),
        add_ids=normalize_and_dedupe_ids(snapshot_update.add_ids, field_name="snapshot_id"),
    )


def validate_update_guards(*, config: ConfigDeploymentBindingUpdate | None, has_snapshot_adds: bool) -> None:
    """Validate update operation guardrails before side effects."""
    if config and config.unbind:
        msg = (
            "Replacing or unbinding deployment configuration/connection via patch is not allowed "
            "for watsonx Orchestrate deployments in Langflow."
        )
        raise InvalidDeploymentOperationError(message=msg)

    if has_snapshot_adds and not (config and (config.config_id is not None or config.raw_payload is not None)):
        msg = "Snapshot add operations require explicit config input. Provide config.config_id or config.raw_payload."
        raise InvalidDeploymentOperationError(message=msg)


def compute_target_tool_sets(
    *,
    agent: dict[str, Any],
    snapshot_ops: SnapshotUpdateOps,
    config: ConfigDeploymentBindingUpdate | None,
) -> tuple[list[str], list[str]]:
    """Return base tool ids and rebinding target ids for config operations."""
    remove_id_set = set(snapshot_ops.remove_ids)
    base_tool_ids = [tool_id for tool_id in extract_agent_tool_ids(agent) if tool_id not in remove_id_set]

    existing_target_tool_ids: list[str] = []
    if config:
        existing_target_tool_ids = dedupe_list([*base_tool_ids, *snapshot_ops.add_ids])
        total_target_count = len(existing_target_tool_ids) + len(snapshot_ops.add_raw_payloads)
        if total_target_count == 0:
            msg = "Config update requires at least one target snapshot tool after removals are applied."
            raise InvalidDeploymentOperationError(message=msg)

    return base_tool_ids, existing_target_tool_ids


def _require_resource_prefix(*, provider_data: dict[str, Any] | None, source_field: str) -> str:
    resource_prefix = str((provider_data or {}).get(PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY) or "").strip()
    if resource_prefix:
        return resource_prefix

    msg = f"provider_data must include '{PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY}' when {source_field} is used."
    raise InvalidContentError(message=msg)


async def resolve_connections_for_update(
    *,
    config: ConfigDeploymentBindingUpdate | None,
    payload_provider_data: dict[str, Any] | None,
    clients: WxOClient,
    user_id: IdLike,
    db: Any,
    client_cache: Any,
    validate_connection_fn: Any = default_validate_connection,
    create_config_fn: Any = default_create_config,
    retry_create_fn: Any = default_retry_create,
) -> tuple[dict[str, str], str | None]:
    """Resolve config app-id -> connection-id mapping for update."""
    resolved_connections: dict[str, str] = {}
    created_app_id: str | None = None
    if not config:
        return resolved_connections, created_app_id

    if config.config_id is not None:
        app_id = str(config.config_id)
        connection = await validate_connection_fn(clients.connections, app_id=app_id)
        return {app_id: connection.connection_id}, created_app_id

    if config.raw_payload is None:
        return resolved_connections, created_app_id

    resource_prefix = _require_resource_prefix(
        provider_data=payload_provider_data,
        source_field="config.raw_payload",
    )
    normalized_config_name = validate_wxo_name(config.raw_payload.name)
    config_app_id = f"{resource_prefix}{normalized_config_name}_app_id"
    config_payload = config.raw_payload.model_copy(update={"name": config_app_id}, deep=True)
    try:
        created_app_id = await retry_create_fn(
            lambda: create_config_fn(
                config=config_payload,
                user_id=user_id,
                db=db,
                client_cache=client_cache,
            )
        )
    except (ClientAPIException, HTTPException) as exc:
        if isinstance(exc, ClientAPIException):
            status_code = exc.response.status_code
            error_detail = str(extract_error_detail(exc.response.text))
        else:
            status_code = exc.status_code
            error_detail = str(extract_error_detail(str(exc.detail)))
        is_conflict = status_code == status.HTTP_409_CONFLICT or "already exists" in error_detail.lower()
        if is_conflict:
            msg = f"{ErrorPrefix.UPDATE.value} error details: {error_detail}"
            raise DeploymentConflictError(message=msg) from None
        raise

    created_connection = await validate_connection_fn(clients.connections, app_id=created_app_id)
    return {created_app_id: created_connection.connection_id}, created_app_id


async def apply_update_mutations_with_rollback(
    *,
    clients: WxOClient,
    user_id: IdLike,
    db: Any,
    client_cache: Any,
    agent_id: str,
    config: ConfigDeploymentBindingUpdate | None,
    payload_provider_data: dict[str, Any] | None,
    snapshot_update: SnapshotDeploymentBindingUpdate | None,
    snapshot_ops: SnapshotUpdateOps,
    base_tool_ids: list[str],
    existing_target_tool_ids: list[str],
    update_payload: dict[str, Any],
    validate_connection_fn: Any = default_validate_connection,
    create_config_fn: Any = default_create_config,
    retry_create_fn: Any = default_retry_create,
    create_and_upload_wxo_flow_tools_fn: Any = default_create_and_upload_wxo_flow_tools,
    update_existing_tool_connection_bindings_fn: Any = default_update_existing_tool_connection_bindings,
    rollback_update_resources_fn: Any = default_rollback_update_resources,
) -> list[str]:
    """Apply update side effects in order with best-effort rollback on failure."""
    created_tool_ids: list[str] = []
    created_app_id: str | None = None
    original_tools: dict[str, dict[str, Any]] = {}
    added_snapshot_ids: list[str] = []
    try:
        resolved_connections, created_app_id = await resolve_connections_for_update(
            config=config,
            payload_provider_data=payload_provider_data,
            clients=clients,
            user_id=user_id,
            db=db,
            client_cache=client_cache,
            validate_connection_fn=validate_connection_fn,
            create_config_fn=create_config_fn,
            retry_create_fn=retry_create_fn,
        )

        if config and snapshot_ops.add_raw_payloads:
            resource_prefix = _require_resource_prefix(
                provider_data=payload_provider_data,
                source_field="snapshot.add_raw_payloads",
            )
            first_app_id = next(iter(resolved_connections.keys()))
            created_tool_ids = await retry_create_fn(
                lambda: create_and_upload_wxo_flow_tools_fn(
                    clients=clients,
                    flow_payloads=snapshot_ops.add_raw_payloads,
                    connections=resolved_connections,
                    app_id=first_app_id,
                    tool_name_prefix=resource_prefix,
                )
            )
            added_snapshot_ids.extend(created_tool_ids)

        if config and existing_target_tool_ids:
            await update_existing_tool_connection_bindings_fn(
                clients=clients,
                existing_target_tool_ids=existing_target_tool_ids,
                resolved_connections=resolved_connections,
                original_tools=original_tools,
            )

        if snapshot_update:
            update_payload["tools"] = dedupe_list([*base_tool_ids, *snapshot_ops.add_ids, *created_tool_ids])
            added_snapshot_ids.extend(snapshot_ops.add_ids)

        if update_payload:
            await retry_create_fn(lambda: asyncio.to_thread(clients.agent.update, agent_id, update_payload))
    except Exception:
        if created_app_id or created_tool_ids or original_tools:
            logger.warning(
                "wxO update failed; rolling back created_tool_ids=%s, created_app_id=%s, mutated_tools=%s",
                created_tool_ids,
                created_app_id,
                list(original_tools.keys()),
            )
            await rollback_update_resources_fn(
                clients=clients,
                created_tool_ids=created_tool_ids,
                created_app_id=created_app_id,
                original_tools=original_tools,
            )
        raise

    return dedupe_list(added_snapshot_ids)
