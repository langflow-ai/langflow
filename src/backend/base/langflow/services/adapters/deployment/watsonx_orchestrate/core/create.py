"""Helpers used to keep wxO deployment create flow lean."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.services.adapters.deployment.exceptions import (
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create,
    rollback_created_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.shared import (
    OrderedUniqueStrs,
    RawConnectionCreatePlan,
    RawToolCreatePlan,
    create_connection_with_conflict_mapping,
    rollback_created_app_ids,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    FlowToolBindingSpec,
    ToolUploadBatchError,
    create_and_upload_wxo_flow_tools_with_bindings,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxBindOperation,
    WatsonxCreateSnapshotBinding,
    WatsonxDeploymentCreatePayload,
    WatsonxFlowArtifactProviderData,
    WatsonxProviderCreateApplyResult,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    build_agent_payload,
    dedupe_list,
    resolve_resource_name_prefix,
    validate_wxo_name,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentData,
        BaseFlowArtifact,
        DeploymentCreate,
        IdLike,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProviderCreatePlan:
    resource_prefix: str
    prefixed_deployment_name: str
    existing_tool_ids: list[str]
    existing_app_ids: list[str]
    raw_connections_to_create: list[RawConnectionCreatePlan]
    raw_tools_to_create: list[RawToolCreatePlan]
    selected_operation_app_ids: list[str]


def validate_provider_create_request_sections(payload: DeploymentCreate) -> None:
    """Reject top-level create sections in watsonx."""
    if payload.snapshot is not None or payload.config is not None:
        msg = (
            "Top-level 'snapshot' and 'config' create sections are no longer supported for "
            "watsonx Orchestrate deployment creation. Use provider_data operations instead."
        )
        raise InvalidDeploymentOperationError(message=msg)


def build_provider_create_plan(
    *,
    deployment_name: str,
    provider_create: WatsonxDeploymentCreatePayload,
) -> ProviderCreatePlan:
    """Build a deterministic CPU-only plan for provider_data create operations."""
    normalized_deployment_name = validate_wxo_name(deployment_name)
    resource_prefix = resolve_resource_name_prefix(caller_prefix=provider_create.resource_name_prefix)
    prefixed_deployment_name = f"{resource_prefix}{normalized_deployment_name}"

    existing_tool_ids = OrderedUniqueStrs.from_values(list(provider_create.tools.existing_ids or []))
    existing_app_ids = OrderedUniqueStrs.from_values(list(provider_create.connections.existing_app_ids or []))
    selected_operation_app_ids = OrderedUniqueStrs()

    raw_tool_app_ids: dict[str, OrderedUniqueStrs] = {}
    for operation in provider_create.operations:
        if not isinstance(operation, WatsonxBindOperation):
            continue
        selected_operation_app_ids.extend(operation.app_ids)
        if operation.tool.reference_id is not None:
            existing_tool_ids.add(operation.tool.reference_id)
            continue
        raw_name = str(operation.tool.name_of_raw)
        raw_apps = raw_tool_app_ids.setdefault(raw_name, OrderedUniqueStrs())
        raw_apps.extend(operation.app_ids)

    raw_connections_to_create = [
        RawConnectionCreatePlan(
            operation_app_id=raw_payload.app_id,
            provider_app_id=f"{resource_prefix}{raw_payload.app_id}",
            payload=raw_payload,
        )
        for raw_payload in (provider_create.connections.raw_payloads or [])
    ]
    raw_tool_pool = {raw_payload.name: raw_payload for raw_payload in (provider_create.tools.raw_payloads or [])}
    raw_tools_to_create = [
        RawToolCreatePlan(raw_name=raw_name, payload=raw_tool_pool[raw_name], app_ids=app_ids.to_list())
        for raw_name, app_ids in raw_tool_app_ids.items()
    ]

    return ProviderCreatePlan(
        resource_prefix=resource_prefix,
        prefixed_deployment_name=prefixed_deployment_name,
        existing_tool_ids=existing_tool_ids.to_list(),
        existing_app_ids=existing_app_ids.to_list(),
        raw_connections_to_create=raw_connections_to_create,
        raw_tools_to_create=raw_tools_to_create,
        selected_operation_app_ids=selected_operation_app_ids.to_list(),
    )


async def apply_provider_create_plan_with_rollback(
    *,
    clients: WxOClient,
    user_id: IdLike,
    db: AsyncSession,
    deployment_spec: BaseDeploymentData,
    plan: ProviderCreatePlan,
) -> WatsonxProviderCreateApplyResult:
    """Apply provider create operations with rollback protection."""
    created_tool_ids: list[str] = []
    created_app_ids: list[str] = []
    created_snapshot_bindings: list[WatsonxCreateSnapshotBinding] = []
    agent_create_response = None
    operation_to_provider_app_id = {app_id: app_id for app_id in plan.existing_app_ids}
    resolved_connections: dict[str, str] = {}

    try:
        if plan.existing_app_ids:
            existing_connections = await asyncio.gather(
                *(
                    retry_create(
                        validate_connection,
                        clients.connections,
                        app_id=app_id,
                    )
                    for app_id in plan.existing_app_ids
                )
            )
            for app_id, connection in zip(plan.existing_app_ids, existing_connections, strict=True):
                resolved_connections[app_id] = connection.connection_id

        if plan.raw_connections_to_create:
            created_connections_results = await asyncio.gather(
                *(
                    create_connection_with_conflict_mapping(
                        clients=clients,
                        app_id=create_plan.provider_app_id,
                        payload=create_plan.payload,
                        user_id=user_id,
                        db=db,
                        error_prefix=ErrorPrefix.CREATE.value,
                    )
                    for create_plan in plan.raw_connections_to_create
                ),
                return_exceptions=True,
            )
            create_connection_errors: list[Exception] = []
            created_app_ids_journal: list[str] = []
            for result in created_connections_results:
                if isinstance(result, BaseException):
                    if isinstance(result, Exception):
                        create_connection_errors.append(result)
                    else:
                        create_connection_errors.append(
                            RuntimeError(
                                f"Connection create failed with non-standard exception: {type(result).__name__}"
                            )
                        )
                    continue
                created_app_ids_journal.append(result)
            created_app_ids.extend(dedupe_list(created_app_ids_journal))
            if create_connection_errors:
                for i, err in enumerate(create_connection_errors):
                    logger.error(
                        "Connection create batch error [%d/%d]: %s",
                        i + 1,
                        len(create_connection_errors),
                        err,
                    )
                raise create_connection_errors[0]
            validated_created_connections = await asyncio.gather(
                *(
                    retry_create(
                        validate_connection,
                        clients.connections,
                        app_id=create_plan.provider_app_id,
                    )
                    for create_plan in plan.raw_connections_to_create
                )
            )
            for create_plan, connection in zip(
                plan.raw_connections_to_create,
                validated_created_connections,
                strict=True,
            ):
                operation_to_provider_app_id[create_plan.operation_app_id] = create_plan.provider_app_id
                resolved_connections[create_plan.provider_app_id] = connection.connection_id

        if plan.raw_tools_to_create:
            tool_bindings = []
            for raw_plan in plan.raw_tools_to_create:
                binding_connections: dict[str, str] = {}
                for operation_app_id in raw_plan.app_ids:
                    provider_app_id = operation_to_provider_app_id.get(operation_app_id)
                    if not provider_app_id:
                        msg = f"No provider app id available for operation app_id '{operation_app_id}'."
                        raise InvalidContentError(message=msg)
                    connection_id = resolved_connections.get(provider_app_id)
                    if not connection_id:
                        msg = f"No resolved connection id available for app_id '{operation_app_id}'."
                        raise InvalidContentError(message=msg)
                    binding_connections[provider_app_id] = connection_id
                tool_bindings.append(
                    FlowToolBindingSpec(
                        flow_payload=raw_plan.payload,
                        connections=binding_connections,
                    )
                )
            try:
                raw_create_results = await create_and_upload_wxo_flow_tools_with_bindings(
                    clients=clients,
                    tool_bindings=tool_bindings,
                    tool_name_prefix=plan.resource_prefix,
                )
            except ToolUploadBatchError as exc:
                created_tool_ids.extend(exc.created_tool_ids)
                for i, err in enumerate(exc.errors):
                    logger.exception("Tool upload batch error [%d/%d]: %s", i + 1, len(exc.errors), err)
                raise exc.errors[0] from exc

            for raw_plan, created_tool_id in zip(plan.raw_tools_to_create, raw_create_results, strict=True):
                tool_id = str(created_tool_id).strip()
                if not tool_id:
                    msg = f"Failed to create tool for raw payload '{raw_plan.raw_name}'."
                    raise InvalidContentError(message=msg)
                created_tool_ids.append(tool_id)
                created_snapshot_bindings.append(
                    WatsonxCreateSnapshotBinding(
                        source_ref=raw_plan.payload.provider_data.source_ref,
                        snapshot_id=tool_id,
                        source_name=str(raw_plan.payload.name).strip() or None,
                        provider_name=f"{plan.resource_prefix}{raw_plan.raw_name}",
                    )
                )

        final_tool_ids = dedupe_list([*plan.existing_tool_ids, *created_tool_ids])
        derived_spec = deployment_spec.model_copy(deep=True)
        if derived_spec.provider_spec is None:
            derived_spec.provider_spec = {}
        derived_spec.provider_spec.update(
            {
                "name": plan.prefixed_deployment_name,
                "display_name": derived_spec.name,
            }
        )
        agent_create_response = await retry_create(
            create_agent_deployment,
            clients=clients,
            data=derived_spec,
            tool_ids=final_tool_ids,
        )
    except Exception:
        logger.warning(
            "wxO create failed; rolling back agent_id=%s, tool_ids=%s, app_ids=%s",
            getattr(agent_create_response, "id", None),
            created_tool_ids,
            created_app_ids,
        )
        last_created_app_id = created_app_ids[-1] if created_app_ids else None
        await rollback_created_resources(
            clients=clients,
            agent_id=getattr(agent_create_response, "id", None),
            tool_ids=created_tool_ids,
            app_id=last_created_app_id,
        )
        if len(created_app_ids) > 1:
            await rollback_created_app_ids(
                clients=clients,
                created_app_ids=created_app_ids[:-1],
            )
        raise

    if not agent_create_response or not getattr(agent_create_response, "id", None):
        msg = f"{ErrorPrefix.CREATE.value} Deployment response was empty."
        raise DeploymentError(message=msg, error_code="deployment_error")

    unique_bound_provider_app_ids = dedupe_list(
        [
            operation_to_provider_app_id[app_id]
            for app_id in plan.selected_operation_app_ids
            if app_id in operation_to_provider_app_id
        ]
    )
    config_id = unique_bound_provider_app_ids[0] if len(unique_bound_provider_app_ids) == 1 else None

    return WatsonxProviderCreateApplyResult(
        agent_id=str(agent_create_response.id),
        config_id=config_id,
        snapshot_ids=created_tool_ids,
        snapshot_bindings=created_snapshot_bindings,
        prefixed_name=plan.prefixed_deployment_name,
        display_name=deployment_spec.name,
    )


async def create_agent_deployment(
    *,
    clients: WxOClient,
    tool_ids: list[str],
    data: BaseDeploymentData,
):
    """Create a provider agent deployment from normalized deployment data."""
    payload = build_agent_payload(
        data=data,
        tool_ids=tool_ids,
    )
    return await asyncio.to_thread(clients.agent.create, payload)


def validate_create_flow_provider_data(
    *,
    payload_schemas: DeploymentPayloadSchemas,
    flow_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]],
) -> list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]]:
    """Validate and normalize flow artifact provider_data via adapter payload slot."""
    slot = payload_schemas.flow_artifact
    if slot is None:
        msg = f"{ErrorPrefix.CREATE.value} Required slot 'flow_artifact' is not configured."
        raise DeploymentError(message=msg, error_code="deployment_error")

    validated_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]] = []
    for flow_payload in flow_payloads:
        provider_data_raw = flow_payload.provider_data if isinstance(flow_payload.provider_data, dict) else {}
        try:
            provider_data = slot.apply(provider_data_raw)
        except AdapterPayloadValidationError as exc:
            msg = (
                "Flow payload must include provider_data with non-empty "
                "'project_id' and 'source_ref' for Watsonx deployment."
            )
            raise InvalidContentError(message=msg) from exc
        validated_payloads.append(flow_payload.model_copy(update={"provider_data": provider_data}))
    return validated_payloads
