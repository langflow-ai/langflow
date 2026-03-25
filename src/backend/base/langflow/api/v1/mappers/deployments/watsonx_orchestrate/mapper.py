"""Watsonx Orchestrate deployment mapper implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentDataUpdate,
    DeploymentCreateResult,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ExecutionStatusResult,
    VerifyCredentials,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreate as AdapterDeploymentCreate,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.adapters.payload import (
    AdapterPayload,
    AdapterPayloadMissingError,
    AdapterPayloadValidationError,
    PayloadSlot,
    PayloadSlotPolicy,
)
from lfx.services.adapters.schema import AdapterType

from langflow.api.v1.mappers.deployments.base import (
    BaseDeploymentMapper,
    DeploymentApiPayloads,
)
from langflow.api.v1.mappers.deployments.contracts import (
    CreatedSnapshotIds,
    CreateFlowArtifactProviderData,
    CreateSnapshotBinding,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBinding,
    UpdateSnapshotBindings,
)
from langflow.api.v1.mappers.deployments.helpers import (
    build_flow_artifacts_from_flow_versions,
    build_project_scoped_flow_artifacts_from_flow_versions,
)
from langflow.api.v1.mappers.deployments.registry import register_mapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiAgentExecutionCreateResultData,
    WatsonxApiAgentExecutionStatusResultData,
    WatsonxApiBindOperation,
    WatsonxApiDeploymentCreatePayload,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
    WatsonxApiFlowArtifactProviderData,
    WatsonxApiRemoveToolOperation,
    WatsonxApiToolAppBinding,
    WatsonxApiUnbindOperation,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentProviderAccountCreateRequest,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    PAYLOAD_SCHEMAS as WXO_ADAPTER_PAYLOAD_SCHEMAS,
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
        deployment_create=PayloadSlot(
            adapter_model=WatsonxApiDeploymentCreatePayload,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        deployment_update=PayloadSlot(
            adapter_model=WatsonxApiDeploymentUpdatePayload,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        deployment_update_result=PayloadSlot(
            adapter_model=WatsonxApiDeploymentUpdateResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        execution_create_result=PayloadSlot(
            adapter_model=WatsonxApiAgentExecutionCreateResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        execution_status_result=PayloadSlot(
            adapter_model=WatsonxApiAgentExecutionStatusResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
    )

    def resolve_provider_tenant_id(self, *, provider_url: str, provider_tenant_id: str | None) -> str | None:
        if provider_tenant_id:
            return provider_tenant_id
        parsed = urlparse(provider_url)
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        try:
            instances_index = path_segments.index("instances")
        except ValueError:
            return None
        account_index = instances_index + 1
        if account_index >= len(path_segments):
            return None
        return path_segments[account_index].strip() or None

    def resolve_verify_credentials(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
    ) -> VerifyCredentials:
        verify_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.verify_credentials
        credentials = {"api_key": payload.api_key.get_secret_value()}
        provider_data = verify_slot.apply(credentials) if verify_slot else credentials
        return VerifyCredentials(
            base_url=payload.provider_url,
            provider_data=provider_data,
        )

    def util_create_flow_artifact_provider_data(
        self,
        *,
        project_id: UUID,
        flow_version_id: UUID,
    ) -> CreateFlowArtifactProviderData:
        return WatsonxApiFlowArtifactProviderData(
            source_ref=str(flow_version_id),
            project_id=str(project_id),
        )

    def util_create_flow_version_ids(self, payload: DeploymentCreateRequest) -> list[UUID]:
        if payload.provider_data is None:
            return []
        api_provider_payload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
        )
        return self._extract_bind_flow_version_ids(api_provider_payload.operations)

    async def resolve_deployment_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentCreate:
        if payload.config is not None or payload.flow_version_ids is not None:
            msg = (
                "Watsonx create does not support top-level 'config' or 'flow_version_ids'. "
                "Use provider_data.operations instead."
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        if payload.provider_data is None:
            msg = "Watsonx create requires provider_data operations."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        api_provider_payload: WatsonxApiDeploymentCreatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
        )
        flow_version_ids = self._extract_bind_flow_version_ids(api_provider_payload.operations)
        flow_artifacts = await build_project_scoped_flow_artifacts_from_flow_versions(
            db=db,
            user_id=user_id,
            project_id=project_id,
            reference_ids=flow_version_ids,
        )
        raw_name_by_flow_version_id = {flow_version_id: artifact.name for flow_version_id, artifact in flow_artifacts}
        provider_operations = self._build_provider_operations(
            operations=api_provider_payload.operations,
            raw_name_by_flow_version_id=raw_name_by_flow_version_id,
        )

        create_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create
        if create_slot is None:
            msg = "Watsonx deployment_create payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        provider_payload: AdapterPayload = create_slot.apply(
            self._build_provider_payload_body(
                resource_name_prefix=api_provider_payload.resource_name_prefix,
                raw_tool_payloads=[
                    artifact.model_copy(
                        update={
                            "provider_data": self.util_create_flow_artifact_provider_data(
                                project_id=project_id,
                                flow_version_id=flow_version_id,
                            ).model_dump(exclude_none=True),
                        }
                    ).model_dump(exclude_none=True)
                    for flow_version_id, artifact in flow_artifacts
                ],
                connections=api_provider_payload.connections,
                operations=provider_operations,
            )
        )
        return AdapterDeploymentCreate(
            spec=payload.spec,
            provider_data=provider_payload,
        )

    async def resolve_deployment_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        payload: DeploymentUpdateRequest,
    ) -> AdapterDeploymentUpdate:
        if (
            payload.config is not None
            or payload.add_flow_version_ids is not None
            or payload.remove_flow_version_ids is not None
        ):
            msg = "Watsonx update does not support top-level 'config'. Use provider_data.operations instead."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        if payload.provider_data is None:  # pure metadata update, e.g., name, description
            return AdapterDeploymentUpdate(spec=payload.spec, provider_data=None)

        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_update,
            slot_name="deployment_update",
            raw=payload.provider_data,
        )
        ordered_flow_version_ids = self._extract_bind_flow_version_ids(api_provider_payload.operations)
        flow_artifacts = await build_flow_artifacts_from_flow_versions(
            db=db,
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            flow_version_ids=ordered_flow_version_ids,
        )
        raw_name_by_flow_version_id = {
            flow_version_id: f"{artifact.name}_v{version_number}"
            for flow_version_id, version_number, _project_id, artifact in flow_artifacts
        }
        raw_payloads = [
            artifact.model_copy(
                update={
                    "name": raw_name_by_flow_version_id[flow_version_id],
                    "provider_data": self.util_create_flow_artifact_provider_data(
                        project_id=project_id,
                        flow_version_id=flow_version_id,
                    ).model_dump(exclude_none=True),
                }
            )
            for flow_version_id, _version_number, project_id, artifact in flow_artifacts
        ]

        existing_tool_flow_version_ids = [
            operation.flow_version_id
            for operation in api_provider_payload.operations
            if isinstance(operation, (WatsonxApiUnbindOperation, WatsonxApiRemoveToolOperation))
        ]
        flow_version_snapshot_id_map = await self._resolve_existing_tool_snapshot_ids(
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            db=db,
            flow_version_ids=list(dict.fromkeys(existing_tool_flow_version_ids)),
        )
        provider_operations = self._build_provider_operations(
            operations=api_provider_payload.operations,
            raw_name_by_flow_version_id=raw_name_by_flow_version_id,
            flow_version_snapshot_id_map=flow_version_snapshot_id_map,
        )

        update_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update
        if update_slot is None:
            msg = "Watsonx deployment_update payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        provider_payload: AdapterPayload = update_slot.apply(
            self._build_provider_payload_body(
                resource_name_prefix=api_provider_payload.resource_name_prefix,
                raw_tool_payloads=[artifact.model_dump(exclude_none=True) for artifact in raw_payloads],
                connections=api_provider_payload.connections,
                operations=provider_operations,
            )
        )
        return AdapterDeploymentUpdate(
            spec=payload.spec,
            provider_data=provider_payload,
        )

    def util_snapshot_ids_to_verify(
        self,
        attachments: list[Any],
    ) -> list[str]:
        return [
            att.provider_snapshot_id
            for att in attachments
            if getattr(att, "provider_snapshot_id", None) and att.provider_snapshot_id.strip()
        ]

    async def resolve_rollback_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        deployment_resource_key: str,
        db: AsyncSession,
    ) -> AdapterDeploymentUpdate | None:
        """Build a compensating update from current DB attachment state.

        Queries flow_version_deployment_attachment for provider_snapshot_ids
        (WXO tool IDs) and constructs an update that declaratively sets the
        agent's tool list to match the (still-committed) DB state.  Also
        restores deployment name/description via spec.

        If the provider snapshots were concurrently deleted, the adapter call
        may fail; read-path snapshot sync handles that residual divergence.
        """
        from langflow.services.database.models.deployment.crud import get_deployment
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            list_deployment_attachments,
        )

        _ = deployment_resource_key
        deployment = await get_deployment(db, user_id=user_id, deployment_id=deployment_db_id)
        if deployment is None:
            return None

        attachments = await list_deployment_attachments(db, user_id=user_id, deployment_id=deployment_db_id)
        existing_tool_ids = [
            str(att.provider_snapshot_id).strip()
            for att in attachments
            if att.provider_snapshot_id and str(att.provider_snapshot_id).strip()
        ]

        update_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update
        if update_slot is None:
            return None
        provider_payload = update_slot.apply({"put_tools": existing_tool_ids})

        return AdapterDeploymentUpdate(
            spec=BaseDeploymentDataUpdate(
                name=deployment.name,
                description=deployment.description or "",
            ),
            provider_data=provider_payload,
        )

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
    ) -> DeploymentUpdateResponse:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider update result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider update result contains invalid provider_result payload.",
        )
        tool_app_bindings = (
            self._to_api_tool_app_bindings(
                adapter_tool_app_bindings=adapter_provider_result.tool_app_bindings,
                adapter_added_snapshot_bindings=adapter_provider_result.added_snapshot_bindings,
            )
            if adapter_provider_result.tool_app_bindings is not None
            else None
        )
        provider_api_result = WatsonxApiDeploymentUpdateResultData(
            created_app_ids=list(adapter_provider_result.created_app_ids),
            tool_app_bindings=tool_app_bindings,
        )
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            name=deployment_row.name,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            provider_data=provider_api_result.model_dump(mode="json", exclude_none=True),
        )

    def util_create_snapshot_bindings(
        self,
        *,
        result: DeploymentCreateResult,
    ) -> CreateSnapshotBindings:
        slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result
        parsed = self._parse_required_payload_slot(
            slot=slot,
            slot_name="deployment_create_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider create result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider create result contains invalid provider_result payload.",
        )
        return CreateSnapshotBindings(
            snapshot_bindings=[
                CreateSnapshotBinding(
                    source_ref=binding.source_ref,
                    snapshot_id=binding.tool_id,
                )
                for binding in parsed.tools_with_refs
            ]
        )

    def util_created_snapshot_ids(
        self,
        *,
        result: DeploymentUpdateResult,
    ) -> CreatedSnapshotIds:
        slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result
        parsed = self._parse_required_payload_slot(
            slot=slot,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider update result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider update result contains invalid provider_result payload.",
        )
        if not parsed.created_snapshot_ids and not parsed.added_snapshot_bindings:
            msg = "Deployment provider update result is missing required snapshot reconciliation bindings."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return CreatedSnapshotIds(ids=parsed.created_snapshot_ids)

    def util_update_snapshot_bindings(
        self,
        *,
        result: DeploymentUpdateResult,
    ) -> UpdateSnapshotBindings:
        slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result
        parsed = self._parse_required_payload_slot(
            slot=slot,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider update result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider update result contains invalid provider_result payload.",
        )
        if not parsed.created_snapshot_ids and not parsed.added_snapshot_bindings:
            msg = "Deployment provider update result is missing required snapshot reconciliation bindings."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return UpdateSnapshotBindings(
            snapshot_bindings=[
                UpdateSnapshotBinding(
                    source_ref=binding.source_ref,
                    snapshot_id=binding.tool_id,
                )
                for binding in parsed.added_snapshot_bindings
            ]
        )

    def util_flow_version_patch(self, payload: DeploymentUpdateRequest) -> FlowVersionPatch:
        if payload.add_flow_version_ids is not None or payload.remove_flow_version_ids is not None:
            msg = (
                "Watsonx flow version patch must be expressed via provider_data.operations. "
                "Top-level 'add_flow_version_ids'/'remove_flow_version_ids' are not supported for this provider."
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        if payload.provider_data is None:
            return FlowVersionPatch()
        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_update,
            slot_name="deployment_update",
            raw=payload.provider_data,
        )
        add_ids = self._extract_bind_flow_version_ids(api_provider_payload.operations)
        remove_ids = list(
            dict.fromkeys(
                operation.flow_version_id
                for operation in api_provider_payload.operations
                if isinstance(operation, (WatsonxApiUnbindOperation, WatsonxApiRemoveToolOperation))
            )
        )
        return FlowVersionPatch(
            add_flow_version_ids=add_ids,
            remove_flow_version_ids=remove_ids,
        )

    def shape_execution_create_result(
        self,
        result: ExecutionCreateResult,
        *,
        deployment_id: UUID,
    ) -> ExecutionCreateResponse:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.execution_create_result,
            slot_name="execution_create_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider execution result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider execution result contains invalid provider_result payload.",
        )
        api_provider_result = WatsonxApiAgentExecutionCreateResultData(
            execution_id=adapter_provider_result.execution_id,
            agent_id=adapter_provider_result.agent_id,
            status=adapter_provider_result.status,
            result=adapter_provider_result.result,
            started_at=adapter_provider_result.started_at,
            completed_at=adapter_provider_result.completed_at,
            failed_at=adapter_provider_result.failed_at,
            cancelled_at=adapter_provider_result.cancelled_at,
            last_error=adapter_provider_result.last_error,
        )
        provider_result = api_provider_result.model_dump(exclude_none=True) or None
        return ExecutionCreateResponse(
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def shape_execution_status_result(
        self,
        result: ExecutionStatusResult,
        *,
        deployment_id: UUID,
    ) -> ExecutionStatusResponse:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.execution_status_result,
            slot_name="execution_status_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider execution result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider execution result contains invalid provider_result payload.",
        )
        api_provider_result = WatsonxApiAgentExecutionStatusResultData(
            execution_id=adapter_provider_result.execution_id,
            agent_id=adapter_provider_result.agent_id,
            status=adapter_provider_result.status,
            result=adapter_provider_result.result,
            started_at=adapter_provider_result.started_at,
            completed_at=adapter_provider_result.completed_at,
            failed_at=adapter_provider_result.failed_at,
            cancelled_at=adapter_provider_result.cancelled_at,
            last_error=adapter_provider_result.last_error,
        )
        provider_result = api_provider_result.model_dump(exclude_none=True) or None
        return ExecutionStatusResponse(
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def _parse_required_payload_slot(
        self,
        *,
        slot: PayloadSlot | None,
        slot_name: str,
        raw: Any,
        missing_payload_detail: str,
        malformed_payload_detail: str,
    ) -> Any:
        if slot is None:
            msg = f"Watsonx {slot_name} payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            return slot.parse(raw)
        except AdapterPayloadMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=missing_payload_detail,
            ) from exc
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{malformed_payload_detail} {detail}",
            ) from exc

    def _parse_api_payload_slot(
        self,
        *,
        slot: PayloadSlot | None,
        slot_name: str,
        raw: Any,
    ) -> Any:
        if slot is None:
            msg = f"Watsonx {slot_name} payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            return slot.parse(raw)
        except AdapterPayloadMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing {slot_name} payload.",
            ) from exc
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid {slot_name} payload: {detail}",
            ) from exc

    def _extract_bind_flow_version_ids(self, operations: list[Any]) -> list[UUID]:
        return list(
            dict.fromkeys(
                operation.flow_version_id for operation in operations if isinstance(operation, WatsonxApiBindOperation)
            )
        )

    def _to_bind_provider_operation(self, *, raw_name: str, app_ids: list[str]) -> AdapterPayload:
        return {
            "op": "bind",
            "tool": {"name_of_raw": raw_name},
            "app_ids": app_ids,
        }

    def _to_unbind_provider_operation(
        self,
        *,
        tool_id: str,
        source_ref: str,
        app_ids: list[str],
    ) -> AdapterPayload:
        return {
            "op": "unbind",
            "tool": {"source_ref": source_ref, "tool_id": tool_id},
            "app_ids": app_ids,
        }

    def _to_remove_tool_provider_operation(self, *, tool_id: str, source_ref: str) -> AdapterPayload:
        return {
            "op": "remove_tool",
            "tool": {"source_ref": source_ref, "tool_id": tool_id},
        }

    def _build_provider_operations(
        self,
        *,
        operations: list[Any],
        raw_name_by_flow_version_id: dict[UUID, str],
        flow_version_snapshot_id_map: dict[UUID, str] | None = None,
    ) -> list[AdapterPayload]:
        provider_operations: list[AdapterPayload] = []
        for operation in operations:
            if isinstance(operation, WatsonxApiBindOperation):
                flow_version_id = operation.flow_version_id
                if flow_version_id not in raw_name_by_flow_version_id:
                    msg = f"bind.flow_version_id not found: [{flow_version_id}]"
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
                provider_operations.append(
                    self._to_bind_provider_operation(
                        raw_name=raw_name_by_flow_version_id[flow_version_id],
                        app_ids=operation.app_ids,
                    )
                )
                continue
            if isinstance(operation, WatsonxApiUnbindOperation):
                flow_version_id = operation.flow_version_id
                if flow_version_snapshot_id_map is None:
                    msg = "Snapshot id map is required for unbind operations."
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
                provider_operations.append(
                    self._to_unbind_provider_operation(
                        tool_id=flow_version_snapshot_id_map[flow_version_id],
                        source_ref=str(flow_version_id),
                        app_ids=operation.app_ids,
                    )
                )
                continue
            if isinstance(operation, WatsonxApiRemoveToolOperation):
                flow_version_id = operation.flow_version_id
                if flow_version_snapshot_id_map is None:
                    msg = "Snapshot id map is required for remove_tool operations."
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
                provider_operations.append(
                    self._to_remove_tool_provider_operation(
                        tool_id=flow_version_snapshot_id_map[flow_version_id],
                        source_ref=str(flow_version_id),
                    )
                )
        return provider_operations

    def _build_provider_payload_body(
        self,
        *,
        resource_name_prefix: str | None,
        raw_tool_payloads: list[dict[str, Any]],
        connections: Any,
        operations: list[AdapterPayload],
    ) -> dict[str, Any]:
        return {
            "resource_name_prefix": resource_name_prefix,
            "tools": {
                "raw_payloads": raw_tool_payloads or None,
            },
            "connections": {
                "existing_app_ids": connections.existing_app_ids,
                "raw_payloads": self._dump_raw_connection_payloads(connections.raw_payloads),
            },
            "operations": operations,
        }

    def _to_api_tool_app_bindings(
        self,
        *,
        adapter_tool_app_bindings: list[Any],
        adapter_added_snapshot_bindings: list[Any],
    ) -> list[WatsonxApiToolAppBinding]:
        tool_id_to_flow_version: dict[str, UUID] = {}
        for binding in adapter_added_snapshot_bindings:
            tool_id = str(binding.tool_id or "").strip()
            source_ref = str(binding.source_ref or "").strip()
            if not tool_id or not source_ref:
                msg = (
                    f"Snapshot binding has empty tool_id={binding.tool_id!r} or "
                    f"source_ref={binding.source_ref!r}; cannot map tool to flow version."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            try:
                tool_id_to_flow_version[tool_id] = UUID(source_ref)
            except ValueError as err:
                msg = (
                    f"Snapshot binding source_ref={source_ref!r} is not a valid UUID "
                    f"for tool_id={tool_id!r}; cannot map tool to flow version."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from err

        api_bindings: list[WatsonxApiToolAppBinding] = []
        for binding in adapter_tool_app_bindings:
            raw_tool_id = str(binding.tool_id or "").strip()
            flow_version_id = tool_id_to_flow_version.get(raw_tool_id)
            if flow_version_id is None:
                msg = (
                    f"tool_app_binding tool_id={raw_tool_id!r} has no matching snapshot "
                    f"binding source_ref; available refs: {sorted(tool_id_to_flow_version)}."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            api_bindings.append(
                WatsonxApiToolAppBinding(
                    flow_version_id=flow_version_id,
                    app_ids=list(binding.app_ids),
                )
            )
        return api_bindings

    def _dump_raw_connection_payloads(self, raw_payloads: list[Any] | None) -> list[dict[str, Any]] | None:
        if not raw_payloads:
            return None
        return [raw_payload.model_dump(exclude_none=True) for raw_payload in raw_payloads]

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
