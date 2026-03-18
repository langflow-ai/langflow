"""Watsonx Orchestrate deployment mapper implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import (
    DeploymentType,
    DeploymentUpdateResult,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.adapters.payload import PayloadSlot, PayloadSlotPolicy
from lfx.services.adapters.schema import AdapterType

from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper, DeploymentApiPayloads
from langflow.api.v1.mappers.deployments.helpers import build_flow_artifacts_from_flow_versions
from langflow.api.v1.mappers.deployments.registry import register_mapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiBindOperation,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
    WatsonxApiRemoveToolOperation,
    WatsonxApiUnbindOperation,
)
from langflow.api.v1.schemas.deployments import DeploymentUpdateRequest, DeploymentUpdateResponse
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxBindOperation,
    WatsonxConnectionRawPayload,
    WatsonxDeploymentUpdatePayload,
    WatsonxRemoveToolOperation,
    WatsonxToolReference,
    WatsonxUnbindOperation,
    WatsonxUpdateConnections,
    WatsonxUpdateTools,
)
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    list_deployment_attachments_for_flow_version_ids,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.database.models.deployment.model import Deployment


@register_mapper(AdapterType.DEPLOYMENT, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
class WatsonxOrchestrateDeploymentMapper(BaseDeploymentMapper):
    """Deployment mapper for Watsonx Orchestrate provider."""

    api_payloads = DeploymentApiPayloads(
        deployment_update=PayloadSlot(
            adapter_model=WatsonxApiDeploymentUpdatePayload,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        deployment_update_result=PayloadSlot(
            adapter_model=WatsonxApiDeploymentUpdateResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
    )

    async def resolve_deployment_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        payload: DeploymentUpdateRequest,
    ) -> AdapterDeploymentUpdate:
        if payload.config is not None:
            msg = "Watsonx update does not support top-level 'config'. Use provider_data.operations instead."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        if payload.provider_data is None:
            return AdapterDeploymentUpdate(spec=payload.spec, provider_data=None)

        slot = self.api_payloads.deployment_update
        if slot is None:
            msg = "Watsonx deployment_update payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        api_provider_payload = slot.parse(payload.provider_data)
        flow_version_ids = [
            operation.tool.flow_version_id
            for operation in api_provider_payload.operations
            if isinstance(operation, WatsonxApiBindOperation) and operation.tool.flow_version_id is not None
        ]
        ordered_flow_version_ids = list(dict.fromkeys(flow_version_ids))
        flow_artifacts = await build_flow_artifacts_from_flow_versions(
            db=db,
            flow_version_ids=ordered_flow_version_ids,
        )
        raw_name_by_flow_version_id = {
            flow_version_id: f"{artifact.name}_v{version_number}"
            for flow_version_id, version_number, artifact in flow_artifacts
        }
        raw_payloads = [
            artifact.model_copy(update={"name": raw_name_by_flow_version_id[flow_version_id]})
            for flow_version_id, _version_number, artifact in flow_artifacts
        ]

        provider_operations: list[WatsonxBindOperation | WatsonxUnbindOperation | WatsonxRemoveToolOperation] = []
        existing_tool_flow_version_ids = [
            operation.tool.flow_version_id
            for operation in api_provider_payload.operations
            if isinstance(operation, (WatsonxApiUnbindOperation, WatsonxApiRemoveToolOperation))
        ]
        flow_version_snapshot_id_map = await self._resolve_existing_tool_snapshot_ids(
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            db=db,
            flow_version_ids=list(dict.fromkeys(existing_tool_flow_version_ids)),
        )
        for operation in api_provider_payload.operations:
            if isinstance(operation, WatsonxApiBindOperation):
                flow_version_id = operation.tool.flow_version_id
                if flow_version_id not in raw_name_by_flow_version_id:
                    msg = f"bind.tool.flow_version_id not found: [{flow_version_id}]"
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
                provider_operations.append(
                    WatsonxBindOperation(
                        op="bind",
                        tool=WatsonxToolReference(name_of_raw=raw_name_by_flow_version_id[flow_version_id]),
                        app_ids=operation.app_ids,
                    )
                )
                continue
            if isinstance(operation, WatsonxApiUnbindOperation):
                flow_version_id = operation.tool.flow_version_id
                provider_operations.append(
                    WatsonxUnbindOperation(
                        op="unbind",
                        tool_id=flow_version_snapshot_id_map[flow_version_id],
                        app_ids=operation.app_ids,
                    )
                )
                continue
            if isinstance(operation, WatsonxApiRemoveToolOperation):
                flow_version_id = operation.tool.flow_version_id
                provider_operations.append(
                    WatsonxRemoveToolOperation(
                        op="remove_tool",
                        tool_id=flow_version_snapshot_id_map[flow_version_id],
                    )
                )

        provider_payload = WatsonxDeploymentUpdatePayload(
            resource_name_prefix=api_provider_payload.resource_name_prefix,
            tools=WatsonxUpdateTools(
                raw_payloads=raw_payloads or None,
            ),
            connections=WatsonxUpdateConnections(
                existing_app_ids=api_provider_payload.connections.existing_app_ids,
                raw_payloads=[
                    WatsonxConnectionRawPayload(**raw_payload.model_dump(exclude_none=True))
                    for raw_payload in (api_provider_payload.connections.raw_payloads or [])
                ]
                or None,
            ),
            operations=provider_operations,
        )
        return AdapterDeploymentUpdate(
            spec=payload.spec,
            provider_data=provider_payload.model_dump(exclude_none=True),
        )

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
        *,
        description: str | None = None,
    ) -> DeploymentUpdateResponse:
        provider_result = self._parse_update_result(result.provider_result)
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            name=deployment_row.name,
            description=description,
            type=DeploymentType(deployment_row.deployment_type or DeploymentType.AGENT.value),
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            provider_data=provider_result.to_api_provider_data(),
        )

    def resolve_created_snapshot_ids(self, result: DeploymentUpdateResult) -> list[str]:
        provider_result = self._parse_update_result(result.provider_result)
        if provider_result.created_snapshot_ids:
            return provider_result.created_snapshot_ids
        return super().resolve_created_snapshot_ids(result)

    def resolve_flow_version_patch(self, payload: DeploymentUpdateRequest) -> tuple[list[UUID], list[UUID]]:
        if payload.flow_version_ids is not None:
            msg = (
                "Watsonx flow version patch must be expressed via provider_data.operations. "
                "Top-level 'flow_version_ids' is not supported for this provider."
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        if payload.provider_data is None:
            return [], []
        slot = self.api_payloads.deployment_update
        if slot is None:
            msg = "Watsonx deployment_update payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        api_provider_payload = slot.parse(payload.provider_data)
        add_ids = list(
            dict.fromkeys(
                operation.tool.flow_version_id
                for operation in api_provider_payload.operations
                if isinstance(operation, WatsonxApiBindOperation)
            )
        )
        remove_ids = list(
            dict.fromkeys(
                operation.tool.flow_version_id
                for operation in api_provider_payload.operations
                if isinstance(operation, (WatsonxApiUnbindOperation, WatsonxApiRemoveToolOperation))
            )
        )
        return add_ids, remove_ids

    def _parse_update_result(self, provider_result: Any) -> WatsonxApiDeploymentUpdateResultData:
        if not isinstance(provider_result, dict):
            return WatsonxApiDeploymentUpdateResultData()
        slot = self.api_payloads.deployment_update_result
        if slot is None:
            msg = "Watsonx deployment_update_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return slot.parse(provider_result)

    async def _resolve_existing_tool_snapshot_ids(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        flow_version_ids: list[UUID],
    ) -> dict[UUID, str]:
        if not flow_version_ids:
            return {}
        attachments = await list_deployment_attachments_for_flow_version_ids(
            db,
            user_id=user_id,
            deployment_id=deployment_db_id,
            flow_version_ids=flow_version_ids,
        )
        flow_version_snapshot_id_map = {
            attachment.flow_version_id: str(attachment.provider_snapshot_id).strip()
            for attachment in attachments
            if isinstance(attachment.provider_snapshot_id, str) and attachment.provider_snapshot_id.strip()
        }
        missing_flow_versions = [
            str(flow_version_id)
            for flow_version_id in flow_version_ids
            if flow_version_id not in flow_version_snapshot_id_map
        ]
        if missing_flow_versions:
            msg = (
                "Cannot resolve provider snapshot ids for flow_version_ids in watsonx operations: "
                f"{missing_flow_versions}"
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        return flow_version_snapshot_id_map
