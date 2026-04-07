"""Watsonx Orchestrate deployment mapper implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentListLlmsResult,
    DeploymentListResult,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ExecutionStatusResult,
    SnapshotListResult,
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
from pydantic import ValidationError

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
    page_offset,
)
from langflow.api.v1.mappers.deployments.registry import register_mapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiAddFlowItem,
    WatsonxApiAgentExecutionCreateResultData,
    WatsonxApiAgentExecutionStatusResultData,
    WatsonxApiConfigListItem,
    WatsonxApiConfigListProviderData,
    WatsonxApiCreatedTool,
    WatsonxApiCreateUpsertToolItem,
    WatsonxApiDeploymentCreatePayload,
    WatsonxApiDeploymentCreateResultData,
    WatsonxApiDeploymentFlowVersionItemData,
    WatsonxApiDeploymentListProviderData,
    WatsonxApiDeploymentLlmListResultData,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
    WatsonxApiFlowArtifactProviderData,
    WatsonxApiProviderDeploymentListItem,
    WatsonxApiSnapshotListProviderData,
    WatsonxApiUpsertFlowItem,
    WatsonxApiUpsertToolItem,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentFlowVersionListItem,
    DeploymentFlowVersionListResponse,
    DeploymentListResponse,
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentSnapshotListResponse,
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
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import normalize_wxo_name
from langflow.services.database.models.deployment_provider_account.utils import extract_tenant_from_url
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    list_deployment_attachments_for_flow_version_ids,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )


@dataclass(frozen=True)
class _NormalizedAttachmentRow:
    attachment: FlowVersionDeploymentAttachment
    flow_version: FlowVersion
    flow_name: str | None
    snapshot_id: str


def _validate_tool_name(name: str) -> str:
    """Normalize and validate a wxO tool name at the API boundary.

    Called for both flow-name-derived defaults and user-provided
    ``tool_name`` overrides on bind operations.  Normalization is
    idempotent (``normalize_wxo_name`` applied downstream in
    ``create_wxo_flow_tool`` is a no-op on already-normalized input).

    Raises ``HTTPException(422)`` when the name cannot produce a valid
    wxO identifier (e.g. empty after sanitisation, starts with a digit).
    This surfaces a clear error to the caller rather than letting the
    ADK or wxO API reject it with a less actionable message.
    """
    normalized = normalize_wxo_name(name)
    if not normalized or not normalized[0].isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Tool name derived from '{name}' is not valid for watsonx Orchestrate. "
                "Names must contain at least one alphanumeric character and start with a letter."
            ),
        )
    return normalized


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
        deployment_list_result=PayloadSlot(
            adapter_model=WatsonxApiDeploymentListProviderData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        config_list_result=PayloadSlot(
            adapter_model=WatsonxApiConfigListProviderData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        config_item_data=PayloadSlot(
            adapter_model=WatsonxApiConfigListItem,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        snapshot_list_result=PayloadSlot(
            adapter_model=WatsonxApiSnapshotListProviderData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        deployment_item_data=PayloadSlot(
            adapter_model=WatsonxApiDeploymentFlowVersionItemData,
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
        deployment_llm_list_result=PayloadSlot(
            adapter_model=WatsonxApiDeploymentLlmListResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
    )

    def resolve_provider_tenant_id(
        self,
        *,
        provider_url: str,
        provider_data: dict[str, Any],
    ) -> str | None:
        tenant_id = self.resolve_provider_tenant_id_from_data(provider_data=provider_data)
        if tenant_id:
            return tenant_id
        return extract_tenant_from_url(provider_url, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)

    def format_conflict_detail(self, raw_message: str) -> str:
        lower = raw_message.lower()
        if "agent" in lower and ("already exists" in lower or "conflict" in lower):
            return (
                "An agent with this name already exists in the provider. "
                "Please choose a different name or delete the existing agent first."
            )
        if ("connection" in lower or "app_id" in lower) and ("already exists" in lower or "conflict" in lower):
            return (
                "A connection referenced in this request already exists in the provider. "
                "Reference it as an existing connection instead of creating a new one."
            )
        if "tool" in lower and ("already exists" in lower or "conflict" in lower):
            return "A tool with this name already exists in the provider. Please choose a different name."
        return super().format_conflict_detail(raw_message)

    def _validate_provider_data(self, provider_data: dict[str, Any]) -> dict[str, Any]:
        verify_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.verify_credentials
        credential_payload = self._credential_provider_data(provider_data)
        if verify_slot:
            validated = verify_slot.apply(credential_payload)
            return validated if isinstance(validated, dict) else dict(validated)
        return credential_payload

    def _credential_provider_data(self, provider_data: dict[str, Any]) -> dict[str, Any]:
        """Return provider_data minus mapper-owned metadata keys."""
        credential_payload: dict[str, Any] = dict(provider_data)
        credential_payload.pop("tenant_id", None)
        return credential_payload

    def resolve_credential_fields(
        self,
        *,
        provider_data: dict[str, Any],
    ) -> dict[str, Any]:
        validated = self._validate_provider_data(provider_data)
        api_key = validated.get("api_key")
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            msg = "provider_data must contain a non-empty 'api_key' string"
            raise ValueError(msg)
        return {"api_key": api_key.strip()}

    def resolve_verify_credentials(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
    ) -> VerifyCredentials:
        validated = self._validate_provider_data(payload.provider_data)
        return VerifyCredentials(
            base_url=payload.url,
            provider_data=validated,
        )

    def resolve_verify_credentials_for_update(
        self,
        *,
        payload: DeploymentProviderAccountUpdateRequest,
        existing_account: DeploymentProviderAccount,
    ) -> VerifyCredentials | None:
        provider_data_changed = "provider_data" in payload.model_fields_set
        if not provider_data_changed:
            return None

        if payload.provider_data is None:
            msg = "'provider_data' cannot be null when provided."
            raise ValueError(msg)
        provider_data = self.resolve_credential_fields(provider_data=payload.provider_data)

        return VerifyCredentials(
            base_url=existing_account.provider_url,
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
        return list(dict.fromkeys(item.flow_version_id for item in api_provider_payload.add_flows))

    def util_existing_deployment_resource_key_for_create(
        self,
        payload: DeploymentCreateRequest,
    ) -> str | None:
        if payload.provider_data is None:
            return None
        api_provider_payload: WatsonxApiDeploymentCreatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
        )
        return api_provider_payload.existing_agent_id

    def util_should_mutate_provider_for_existing_deployment_create(
        self,
        payload: DeploymentCreateRequest,
    ) -> bool:
        if payload.provider_data is None:
            return False
        api_provider_payload: WatsonxApiDeploymentCreatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
        )
        return bool(api_provider_payload.add_flows or api_provider_payload.upsert_tools)

    def util_create_result_from_existing_update(
        self,
        *,
        existing_resource_key: str,
        result: DeploymentUpdateResult,
    ) -> DeploymentCreateResult:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider update result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider update result contains invalid provider_result payload.",
        )
        create_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result
        if create_slot is None:
            msg = "Watsonx deployment_create_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            create_provider_result = create_slot.apply(
                {
                    "app_ids": list(adapter_provider_result.created_app_ids),
                    "tools_with_refs": [
                        {"source_ref": binding.source_ref, "tool_id": binding.tool_id}
                        for binding in adapter_provider_result.created_snapshot_bindings
                    ],
                }
            )
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Deployment provider update result cannot be normalized for create response: {detail}",
            ) from exc
        return DeploymentCreateResult(
            id=existing_resource_key,
            provider_result=create_provider_result,
        )

    async def _resolve_provider_payload_from_create_api(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
        slot: PayloadSlot | None,
        slot_name: str,
    ) -> AdapterPayload:
        if payload.provider_data is None:
            msg = "Watsonx create requires provider_data operations."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        api_provider_payload: WatsonxApiDeploymentCreatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
        )
        flow_version_ids = list(dict.fromkeys(item.flow_version_id for item in api_provider_payload.add_flows))
        flow_artifacts = await build_project_scoped_flow_artifacts_from_flow_versions(
            db=db,
            user_id=user_id,
            project_id=project_id,
            reference_ids=flow_version_ids,
        )
        # Start with flow names as defaults, then let user-provided tool_name
        # overrides replace them. Validation runs on the final map so that an
        # invalid flow name doesn't block a user who provided a valid custom
        # tool_name for that flow.
        raw_name_by_flow_version_id: dict[UUID, str] = {
            flow_version_id: artifact.name for flow_version_id, artifact in flow_artifacts
        }
        for item in api_provider_payload.add_flows:
            if item.tool_name:
                raw_name_by_flow_version_id[item.flow_version_id] = item.tool_name
        for fv_id, name in raw_name_by_flow_version_id.items():
            raw_name_by_flow_version_id[fv_id] = _validate_tool_name(name)
        provider_operations = self._build_provider_operations(
            add_flows=api_provider_payload.add_flows,
            upsert_tools=api_provider_payload.upsert_tools,
            raw_name_by_flow_version_id=raw_name_by_flow_version_id,
        )
        if slot is None:
            msg = f"Watsonx {slot_name} payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            return slot.apply(
                self._build_provider_payload_body(
                    llm=api_provider_payload.llm,
                    raw_tool_payloads=[
                        artifact.model_copy(
                            update={
                                "name": raw_name_by_flow_version_id[flow_version_id],
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
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_data payload: {detail}",
            ) from exc

    async def resolve_deployment_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentCreate:
        provider_payload = await self._resolve_provider_payload_from_create_api(
            user_id=user_id,
            project_id=project_id,
            db=db,
            payload=payload,
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create,
            slot_name="deployment_create",
        )
        return AdapterDeploymentCreate(
            spec=BaseDeploymentData(
                name=payload.name,
                description=payload.description,
                type=payload.type,
            ),
            provider_data=provider_payload,
        )

    async def resolve_deployment_update_for_existing_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentUpdate:
        provider_payload = await self._resolve_provider_payload_from_create_api(
            user_id=user_id,
            project_id=project_id,
            db=db,
            payload=payload,
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update,
            slot_name="deployment_update",
        )
        return AdapterDeploymentUpdate(
            spec=BaseDeploymentDataUpdate(
                name=payload.name,
                description=payload.description,
            ),
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
        adapter_spec = (
            BaseDeploymentDataUpdate(
                name=payload.name,
                description=payload.description,
            )
            if payload.name is not None or payload.description is not None
            else None
        )
        if payload.provider_data is None:  # pure metadata update, e.g., name, description
            return AdapterDeploymentUpdate(spec=adapter_spec, provider_data=None)

        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_update,
            slot_name="deployment_update",
            raw=payload.provider_data,
        )
        ordered_flow_version_ids = list(
            dict.fromkeys(
                item.flow_version_id
                for item in api_provider_payload.upsert_flows
                if item.add_app_ids or not item.remove_app_ids
            )
        )
        flow_artifacts = await build_flow_artifacts_from_flow_versions(
            db=db,
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            flow_version_ids=ordered_flow_version_ids,
        )
        # Start with normalized flow names as defaults, then let user-provided
        # tool_name overrides replace them. Validation runs on the final map
        # so that an invalid flow name doesn't block a user who provided a
        # valid custom tool_name for that flow.
        raw_name_by_flow_version_id: dict[UUID, str] = {
            flow_version_id: artifact.name for flow_version_id, _version_number, _project_id, artifact in flow_artifacts
        }
        # Override with user-provided tool names when present
        for item in api_provider_payload.upsert_flows:
            if item.tool_name and item.flow_version_id in raw_name_by_flow_version_id:
                raw_name_by_flow_version_id[item.flow_version_id] = item.tool_name
        for fv_id, name in raw_name_by_flow_version_id.items():
            raw_name_by_flow_version_id[fv_id] = _validate_tool_name(name)
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

        upsert_fv_ids = list(dict.fromkeys(item.flow_version_id for item in api_provider_payload.upsert_flows))
        remove_fv_ids = list(dict.fromkeys(api_provider_payload.remove_flows))
        all_fv_ids = list(dict.fromkeys(upsert_fv_ids + remove_fv_ids))
        flow_version_snapshot_id_map = await self._lookup_snapshot_ids(
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            db=db,
            flow_version_ids=all_fv_ids,
        )
        strict_fv_ids = list(
            dict.fromkeys(
                [item.flow_version_id for item in api_provider_payload.upsert_flows if item.remove_app_ids]
                + remove_fv_ids
            )
        )
        missing_strict = [str(fv) for fv in strict_fv_ids if fv not in flow_version_snapshot_id_map]
        if missing_strict:
            msg = f"Cannot resolve provider snapshot ids for flow_version_ids in watsonx operations: {missing_strict}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        reused_fv_ids = {
            item.flow_version_id
            for item in api_provider_payload.upsert_flows
            if (item.add_app_ids or not item.remove_app_ids) and item.flow_version_id in flow_version_snapshot_id_map
        }
        filtered_raw_payloads = (
            [
                raw_payload
                for (flow_version_id, _version_number, _project_id, _artifact), raw_payload in zip(
                    flow_artifacts, raw_payloads, strict=True
                )
                if flow_version_id not in reused_fv_ids
            ]
            if reused_fv_ids
            else raw_payloads
        )

        provider_operations = self._build_provider_operations(
            upsert_flows=api_provider_payload.upsert_flows,
            upsert_tools=api_provider_payload.upsert_tools,
            remove_flows=api_provider_payload.remove_flows,
            remove_tools=api_provider_payload.remove_tools,
            raw_name_by_flow_version_id=raw_name_by_flow_version_id,
            flow_version_snapshot_id_map=flow_version_snapshot_id_map,
        )

        update_slot = WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update
        if update_slot is None:
            msg = "Watsonx deployment_update payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            provider_payload: AdapterPayload = update_slot.apply(
                self._build_provider_payload_body(
                    llm=api_provider_payload.llm,
                    raw_tool_payloads=[artifact.model_dump(exclude_none=True) for artifact in filtered_raw_payloads],
                    connections=api_provider_payload.connections,
                    operations=provider_operations,
                )
            )
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_data payload: {detail}",
            ) from exc
        return AdapterDeploymentUpdate(
            spec=adapter_spec,
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

    def shape_deployment_create_result(
        self,
        result: DeploymentCreateResult,
        deployment_row: Deployment,
        *,
        provider_key: str,
    ) -> DeploymentCreateResponse:
        """Shape create result provider_data with created-tools semantics.

        ``created_tools`` is populated directly from ``tools_with_refs``. Each
        entry must carry a flow-version UUID ``source_ref`` and a non-empty
        provider ``tool_id``.
        """
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result,
            slot_name="deployment_create_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider create result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider create result contains invalid provider_result payload.",
        )
        created_tools: list[WatsonxApiCreatedTool] = []
        for binding in adapter_provider_result.tools_with_refs:
            tool_id = str(binding.tool_id or "").strip()
            source_ref = str(binding.source_ref or "").strip()
            if not tool_id:
                msg = "Deployment provider create result contains a tool binding with an empty tool_id."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            if not source_ref:
                msg = (
                    "Deployment provider create result contains a tool binding with an empty source_ref "
                    f"for tool_id={tool_id!r}."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            try:
                created_tool = WatsonxApiCreatedTool(
                    flow_version_id=source_ref,
                    tool_id=tool_id,
                )
            except ValidationError as exc:
                msg = (
                    "Deployment provider create result contains a created tool binding with a non-UUID "
                    f"source_ref={source_ref!r} for tool_id={tool_id!r}. A flow version id was expected."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc
            created_tools.append(created_tool)
        provider_api_result = WatsonxApiDeploymentCreateResultData(
            created_app_ids=list(adapter_provider_result.app_ids),
            created_tools=created_tools,
        )
        return DeploymentCreateResponse(
            id=deployment_row.id,
            provider_id=deployment_row.deployment_provider_account_id,
            provider_key=provider_key,
            name=deployment_row.name,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            resource_key=deployment_row.resource_key,
            provider_data=provider_api_result.to_api_provider_data(),
        )

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
        *,
        provider_key: str,
    ) -> DeploymentUpdateResponse:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider update result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider update result contains invalid provider_result payload.",
        )
        created_tools = self._to_api_created_tools(
            adapter_created_snapshot_bindings=adapter_provider_result.created_snapshot_bindings
        )
        provider_api_result = WatsonxApiDeploymentUpdateResultData(
            created_app_ids=list(adapter_provider_result.created_app_ids),
            created_tools=created_tools,
        )
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            provider_id=deployment_row.deployment_provider_account_id,
            provider_key=provider_key,
            name=deployment_row.name,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            resource_key=deployment_row.resource_key,
            provider_data=provider_api_result.model_dump(mode="json", exclude_none=True),
        )

    def shape_llm_list_result(self, result: DeploymentListLlmsResult) -> DeploymentLlmListResponse:
        adapter_provider_result = self._parse_required_payload_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_llm_list_result,
            slot_name="deployment_llm_list_result",
            raw=result.provider_result,
            missing_payload_detail="Deployment provider llm list result is missing provider_result payload.",
            malformed_payload_detail="Deployment provider llm list result contains invalid provider_result payload.",
        )
        api_slot = self.api_payloads.deployment_llm_list_result
        if api_slot is None:
            msg = "Watsonx deployment_llm_list_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:  # straight pass-through today, so just dump + validate
            api_provider_result: WatsonxApiDeploymentLlmListResultData = api_slot.parse(
                adapter_provider_result.model_dump(exclude_none=True)
            )
        except AdapterPayloadMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Deployment mapper llm list result payload is missing.",
            ) from exc
        except AdapterPayloadValidationError as exc:
            detail = exc.format_first_error()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Deployment mapper llm list result payload is invalid: {detail}",
            ) from exc
        return DeploymentLlmListResponse(provider_data=api_provider_result.model_dump(mode="json", exclude_none=True))

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
        """Extract snapshot bindings for attachment reconciliation.

        Only bindings whose ``source_ref`` is a valid UUID are included.
        Tool-id-based operations produce bindings with non-UUID
        ``source_ref`` values (the provider tool_id itself); these are
        excluded because they do not create or modify
        ``flow_version_deployment_attachment`` records.
        """
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

        flow_version_bindings: list[UpdateSnapshotBinding] = []
        for binding in parsed.added_snapshot_bindings:
            try:
                UUID(binding.source_ref)
            except (ValueError, AttributeError):
                continue
            flow_version_bindings.append(
                UpdateSnapshotBinding(
                    source_ref=binding.source_ref,
                    snapshot_id=binding.tool_id,
                )
            )
        return UpdateSnapshotBindings(snapshot_bindings=flow_version_bindings)

    def util_flow_version_patch(self, payload: DeploymentUpdateRequest) -> FlowVersionPatch:
        if payload.provider_data is None:
            return FlowVersionPatch()
        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self._parse_api_payload_slot(
            slot=self.api_payloads.deployment_update,
            slot_name="deployment_update",
            raw=payload.provider_data,
        )
        add_ids = list(
            dict.fromkeys(
                item.flow_version_id
                for item in api_provider_payload.upsert_flows
                if item.add_app_ids or not item.remove_app_ids
            )
        )
        remove_ids = list(dict.fromkeys(api_provider_payload.remove_flows))
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
            thread_id=adapter_provider_result.thread_id,
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
            thread_id=adapter_provider_result.thread_id,
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

    def shape_deployment_list_result(
        self,
        result: DeploymentListResult,
    ) -> DeploymentListResponse:
        provider_result = {
            "deployments": [
                self._shape_provider_deployment_list_entry(item) for item in result.deployments if str(item.id).strip()
            ]
        }
        slot = self.api_payloads.deployment_list_result
        if slot is None:
            msg = "Watsonx deployment_list_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            validated_payload = slot.apply(provider_result)
        except AdapterPayloadValidationError as exc:
            first_error = exc.error.errors()[0] if exc.error.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid deployment list provider_data payload: {detail}",
            ) from exc
        return DeploymentListResponse(
            deployments=None,
            provider_data=validated_payload,
        )

    def shape_config_list_result(
        self,
        result: ConfigListResult,
        *,
        page: int,
        size: int,
    ) -> DeploymentConfigListResponse:
        slot = self.api_payloads.config_list_result
        if slot is None:
            msg = "Watsonx config_list_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)

        items_all: list[WatsonxApiConfigListItem] = []
        for item in result.configs:
            if not isinstance(item.provider_data, dict):
                msg = "Invalid config item provider_data payload: expected non-null object."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            items_all.append(
                self.shape_config_item_data(
                    {
                        **item.provider_data,
                        "connection_id": item.id,
                        "app_id": item.name,
                    }
                )
            )
        total = len(items_all)
        offset = page_offset(page, size)
        provider_payload = {
            "connections": [
                item.model_dump(mode="json", exclude_none=True) for item in items_all[offset : offset + size]
            ],
            "page": page,
            "size": size,
            "total": total,
        }
        try:
            validated_payload = slot.parse(provider_payload).model_dump(mode="json", exclude_none=True)
        except AdapterPayloadValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid config list provider_data payload: {exc.format_first_error()}",
            ) from exc

        return DeploymentConfigListResponse(provider_data=validated_payload or None)

    def shape_snapshot_list_result(
        self,
        result: SnapshotListResult,
        *,
        page: int,
        size: int,
    ) -> DeploymentSnapshotListResponse:
        slot = self.api_payloads.snapshot_list_result
        if slot is None:
            msg = "Watsonx snapshot_list_result payload slot is not configured."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)

        items_all: list[dict[str, Any]] = []
        for item in result.snapshots:
            item_provider_data = item.provider_data if isinstance(item.provider_data, dict) else {}
            connections = item_provider_data.get("connections")
            items_all.append(
                {
                    "id": str(item.id).strip(),
                    "name": str(item.name or "").strip(),
                    "connections": connections if isinstance(connections, dict) else {},
                }
            )

        total = len(items_all)
        offset = page_offset(page, size)
        provider_payload = {
            "tools": items_all[offset : offset + size],
            "page": page,
            "size": size,
            "total": total,
        }
        try:
            validated_payload = slot.parse(provider_payload).model_dump(mode="json", exclude_none=True)
        except AdapterPayloadValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid snapshot list provider_data payload: {exc.format_first_error()}",
            ) from exc

        return DeploymentSnapshotListResponse(provider_data=validated_payload or None)

    def shape_flow_version_list_result(
        self,
        *,
        rows: list[tuple[FlowVersionDeploymentAttachment, FlowVersion, str | None]],
        snapshot_result: SnapshotListResult | None,
        page: int,
        size: int,
        total: int,
    ) -> DeploymentFlowVersionListResponse:
        normalized_rows = self._normalize_flow_version_attachment_rows(rows)
        snapshot_data_by_id = self._resolve_snapshot_data_by_id(
            snapshot_result=snapshot_result,
        )
        snapshot_name_by_id = self._resolve_snapshot_name_by_id(
            snapshot_result=snapshot_result,
        )

        flow_versions = [
            DeploymentFlowVersionListItem(
                id=row.flow_version.id,
                flow_id=row.flow_version.flow_id,
                flow_name=row.flow_name,
                version_number=row.flow_version.version_number,
                attached_at=row.attachment.created_at,
                provider_snapshot_id=row.snapshot_id,
                provider_data=self.shape_deployment_flow_version_item_data(
                    snapshot_data=snapshot_data_by_id.get(row.snapshot_id),
                    tool_name=snapshot_name_by_id.get(row.snapshot_id),
                ),
            )
            for row in normalized_rows
        ]

        return DeploymentFlowVersionListResponse(
            flow_versions=flow_versions,
            page=page,
            size=size,
            total=total,
        )

    def _normalize_flow_version_attachment_rows(
        self,
        rows: list[tuple[FlowVersionDeploymentAttachment, FlowVersion, str | None]],
    ) -> list[_NormalizedAttachmentRow]:
        normalized_rows: list[_NormalizedAttachmentRow] = []
        for attachment, flow_version, flow_name in rows:
            snapshot_id = (attachment.provider_snapshot_id or "").strip()
            if not snapshot_id:
                msg = "Flow version attachment has an invalid provider_snapshot_id."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            normalized_rows.append(
                _NormalizedAttachmentRow(
                    attachment=attachment,
                    flow_version=flow_version,
                    flow_name=flow_name,
                    snapshot_id=snapshot_id,
                )
            )
        return normalized_rows

    def _resolve_snapshot_data_by_id(
        self,
        *,
        snapshot_result: SnapshotListResult | None,
    ) -> dict[str, dict[str, Any] | None]:
        if snapshot_result is None:
            return {}
        if not snapshot_result.snapshots:
            return {}

        snapshot_data_by_id: dict[str, dict[str, Any] | None] = {}
        for snapshot in snapshot_result.snapshots:
            snapshot_id = str(snapshot.id).strip()
            if not snapshot_id:
                continue
            provider_data = snapshot.provider_data
            snapshot_data_by_id[snapshot_id] = provider_data if isinstance(provider_data, dict) else None

        return snapshot_data_by_id

    @staticmethod
    def _resolve_snapshot_name_by_id(
        *,
        snapshot_result: SnapshotListResult | None,
    ) -> dict[str, str]:
        """Map snapshot IDs to their provider tool names.

        The tool name is the wxO-side name, which may differ from the
        Langflow flow name if the user provided a custom ``tool_name``
        at deploy time or renamed the tool directly in the wxO console.

        Edge cases:
        - Provider unreachable / snapshot_result is None: returns ``{}``.
          ``provider_data.tool_name`` will be absent/``None`` and the frontend
          falls back to the Langflow flow name for display.
        - Tool renamed in wxO console: the new name is returned here since
          ``snapshot_result`` is fetched fresh on each request.
        - Tool deleted in wxO: missing from ``snapshot_result.snapshots``,
          so no entry in the returned dict. ``provider_data.tool_name`` will be
          absent/``None``.
        """
        if not snapshot_result or not snapshot_result.snapshots:
            return {}
        result: dict[str, str] = {}
        for snapshot in snapshot_result.snapshots:
            snapshot_id = str(snapshot.id).strip()
            name = str(snapshot.name or "").strip()
            if snapshot_id and name:
                result[snapshot_id] = name
        return result

    def shape_deployment_flow_version_item_data(
        self,
        *,
        snapshot_data: dict[str, Any] | None,
        tool_name: str | None = None,
    ) -> dict[str, Any] | None:
        raw_connections = snapshot_data.get("connections") if snapshot_data else None
        app_ids = list(raw_connections.keys()) if isinstance(raw_connections, dict) else []
        if not app_ids and not tool_name:
            return None
        try:
            return self._validate_slot(
                self.api_payloads.deployment_item_data,
                {
                    "app_ids": app_ids,
                    "tool_name": tool_name,
                },
            )
        except AdapterPayloadValidationError as exc:
            detail = exc.format_first_error()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid flow-version provider_data payload: {detail}",
            ) from exc

    def _shape_provider_deployment_list_entry(self, item: Any) -> dict[str, Any]:
        item_provider_data = item.provider_data
        if item_provider_data is not None and not isinstance(item_provider_data, dict):
            msg = "Invalid deployment list item provider_data payload: expected object or null."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            return WatsonxApiProviderDeploymentListItem.model_validate(
                {
                    "id": str(item.id),
                    "name": item.name,
                    "type": item.type,
                    "description": getattr(item, "description", None),
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    **(item_provider_data or {}),
                }
            ).model_dump(
                mode="json",
                exclude_none=True,
            )
        except ValidationError as exc:
            first_error = exc.errors()[0] if exc.errors() else {}
            detail = str(first_error.get("msg") or exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid deployment list item provider_data payload: {detail}",
            ) from exc

    def shape_config_item_data(self, provider_data: dict[str, Any]) -> WatsonxApiConfigListItem:
        return self._parse_required_payload_slot(
            slot=self.api_payloads.config_item_data,
            slot_name="config_item_data",
            raw=provider_data,
            missing_payload_detail="Config item provider_data payload is missing.",
            malformed_payload_detail="Invalid config item provider_data payload:",
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
            detail = exc.format_first_error()
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
                detail="Missing provider_data payload.",
            ) from exc
        except AdapterPayloadValidationError as exc:
            detail = exc.format_first_error()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_data payload: {detail}",
            ) from exc

    def _to_bind_provider_operation(self, *, raw_name: str, app_ids: list[str]) -> AdapterPayload:
        return {
            "op": "bind",
            "tool": {"name_of_raw": raw_name},
            "app_ids": app_ids,
        }

    def _to_bind_existing_tool_provider_operation(
        self,
        *,
        tool_id: str,
        source_ref: str,
        app_ids: list[str],
    ) -> AdapterPayload:
        """Bind operation that reuses an existing tool via tool_id_with_ref."""
        return {
            "op": "bind",
            "tool": {"tool_id_with_ref": {"source_ref": source_ref, "tool_id": tool_id}},
            "app_ids": app_ids,
        }

    def _to_attach_tool_provider_operation(self, *, tool_id: str, source_ref: str) -> AdapterPayload:
        """Attach an existing tool to the agent without connection bindings."""
        return {
            "op": "attach_tool",
            "tool": {"source_ref": source_ref, "tool_id": tool_id},
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
        add_flows: list[WatsonxApiAddFlowItem] | None = None,
        upsert_flows: list[WatsonxApiUpsertFlowItem] | None = None,
        upsert_tools: list[WatsonxApiUpsertToolItem] | list[WatsonxApiCreateUpsertToolItem] | None = None,
        remove_flows: list[UUID] | None = None,
        remove_tools: list[str] | None = None,
        raw_name_by_flow_version_id: dict[UUID, str],
        flow_version_snapshot_id_map: dict[UUID, str] | None = None,
    ) -> list[AdapterPayload]:
        provider_operations: list[AdapterPayload] = []
        add_flows = add_flows or []
        upsert_flows = upsert_flows or []
        upsert_tools = upsert_tools or []
        remove_flows = remove_flows or []
        remove_tools = remove_tools or []

        # Create path flow semantics.
        for item in add_flows:
            flow_version_id = item.flow_version_id
            existing_tool_id = (flow_version_snapshot_id_map or {}).get(flow_version_id)
            if existing_tool_id:
                if item.app_ids:
                    provider_operations.append(
                        self._to_bind_existing_tool_provider_operation(
                            tool_id=existing_tool_id,
                            source_ref=str(flow_version_id),
                            app_ids=item.app_ids,
                        )
                    )
                else:
                    provider_operations.append(
                        self._to_attach_tool_provider_operation(
                            tool_id=existing_tool_id,
                            source_ref=str(flow_version_id),
                        )
                    )
                continue

            if flow_version_id not in raw_name_by_flow_version_id:
                msg = f"add_flows.flow_version_id not found: [{flow_version_id}]"
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
            if not item.app_ids:
                # Raw tool is still created via tools.raw_payloads;
                # no provider bind operation needed.
                continue
            provider_operations.append(
                self._to_bind_provider_operation(
                    raw_name=raw_name_by_flow_version_id[flow_version_id],
                    app_ids=item.app_ids,
                )
            )

        # Update path flow semantics.
        for item in upsert_flows:
            flow_version_id = item.flow_version_id
            existing_tool_id = (flow_version_snapshot_id_map or {}).get(flow_version_id)
            if existing_tool_id:
                if item.add_app_ids:
                    provider_operations.append(
                        self._to_bind_existing_tool_provider_operation(
                            tool_id=existing_tool_id,
                            source_ref=str(flow_version_id),
                            app_ids=item.add_app_ids,
                        )
                    )
                elif not item.remove_app_ids:
                    # Empty add/remove means ensure attached.
                    provider_operations.append(
                        self._to_attach_tool_provider_operation(
                            tool_id=existing_tool_id,
                            source_ref=str(flow_version_id),
                        )
                    )
                if item.remove_app_ids:
                    provider_operations.append(
                        self._to_unbind_provider_operation(
                            tool_id=existing_tool_id,
                            source_ref=str(flow_version_id),
                            app_ids=item.remove_app_ids,
                        )
                    )
                if item.tool_name:
                    provider_operations.append(
                        {
                            "op": "rename_tool",
                            "tool": {
                                "source_ref": str(flow_version_id),
                                "tool_id": existing_tool_id,
                            },
                            "new_name": _validate_tool_name(item.tool_name),
                        }
                    )
                continue

            if item.remove_app_ids:
                msg = (
                    "Cannot resolve provider snapshot ids for flow_version_ids "
                    f"in watsonx operations: [{flow_version_id}]"
                )
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
            if flow_version_id not in raw_name_by_flow_version_id:
                msg = f"upsert_flows.flow_version_id not found: [{flow_version_id}]"
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
            if item.add_app_ids:
                provider_operations.append(
                    self._to_bind_provider_operation(
                        raw_name=raw_name_by_flow_version_id[flow_version_id],
                        app_ids=item.add_app_ids,
                    )
                )

        # Update flow removals.
        for flow_version_id in remove_flows:
            if flow_version_snapshot_id_map is None or flow_version_id not in flow_version_snapshot_id_map:
                msg = (
                    "Cannot resolve provider snapshot ids for flow_version_ids "
                    f"in watsonx operations: [{flow_version_id}]"
                )
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
            provider_operations.append(
                self._to_remove_tool_provider_operation(
                    tool_id=flow_version_snapshot_id_map[flow_version_id],
                    source_ref=str(flow_version_id),
                )
            )

        # Tool-id-based semantics (create + update).
        for item in upsert_tools:
            tool_id = item.tool_id.strip()
            remove_app_ids = getattr(item, "remove_app_ids", []) or []
            if item.add_app_ids:
                provider_operations.append(
                    self._to_bind_existing_tool_provider_operation(
                        tool_id=tool_id,
                        source_ref=tool_id,
                        app_ids=item.add_app_ids,
                    )
                )
            elif not remove_app_ids:
                provider_operations.append(
                    self._to_attach_tool_provider_operation(
                        tool_id=tool_id,
                        source_ref=tool_id,
                    )
                )
            if remove_app_ids:
                provider_operations.append(
                    self._to_unbind_provider_operation(
                        tool_id=tool_id,
                        source_ref=tool_id,
                        app_ids=remove_app_ids,
                    )
                )

        for tool_id in remove_tools:
            normalized_tool_id = str(tool_id).strip()
            provider_operations.append(
                self._to_remove_tool_provider_operation(
                    tool_id=normalized_tool_id,
                    source_ref=normalized_tool_id,
                )
            )

        return provider_operations

    def _build_provider_payload_body(
        self,
        *,
        llm: str | None,
        raw_tool_payloads: list[dict[str, Any]],
        connections: list[Any],
        operations: list[AdapterPayload],
    ) -> dict[str, Any]:
        payload = {
            "tools": {
                "raw_payloads": raw_tool_payloads or None,
            },
            "connections": {
                "raw_payloads": self._dump_key_value_connection_payloads(connections),
            },
            "operations": operations,
        }
        if llm is not None:
            payload["llm"] = llm
        return payload

    def _to_api_created_tools(
        self,
        *,
        adapter_created_snapshot_bindings: list[Any],
    ) -> list[WatsonxApiCreatedTool]:
        """Map adapter created snapshot bindings to API ``created_tools``."""
        created_tools: list[WatsonxApiCreatedTool] = []
        for binding in adapter_created_snapshot_bindings:
            tool_id = str(binding.tool_id or "").strip()
            source_ref = str(binding.source_ref or "").strip()
            if not tool_id or not source_ref:
                msg = (
                    f"Created snapshot binding has empty tool_id={binding.tool_id!r} or "
                    f"source_ref={binding.source_ref!r}; cannot map tool binding."
                )
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            try:
                created_tool = WatsonxApiCreatedTool(
                    flow_version_id=source_ref,
                    tool_id=tool_id,
                )
            except ValidationError as exc:
                msg = f"Created snapshot binding has non-UUID source_ref={source_ref!r} for tool_id={tool_id!r}."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc
            created_tools.append(created_tool)
        return created_tools

    def _dump_key_value_connection_payloads(self, key_value_payloads: list[Any] | None) -> list[dict[str, Any]] | None:
        if not key_value_payloads:
            return None
        normalized: list[dict[str, Any]] = []
        for payload in key_value_payloads:
            item: dict[str, Any] = {"app_id": payload.app_id}
            environment_variables = self._to_adapter_environment_variables(payload.credentials)
            if environment_variables is not None:
                item["environment_variables"] = environment_variables
            normalized.append(item)
        return normalized

    def _to_adapter_environment_variables(self, credentials: list[Any] | None) -> dict[str, dict[str, Any]] | None:
        if not credentials:
            return None
        return {
            credential.key: {
                "value": credential.value,
                "source": credential.source,
            }
            for credential in credentials
        }

    async def _lookup_snapshot_ids(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        flow_version_ids: list[UUID],
    ) -> dict[UUID, str]:
        """Raw DB lookup of flow_version -> provider_snapshot_id.

        Returns a partial map -- only entries with a non-empty
        ``provider_snapshot_id`` are included.  Callers decide whether
        missing entries are an error or expected.
        """
        if not flow_version_ids:
            return {}
        attachments = await list_deployment_attachments_for_flow_version_ids(
            db,
            user_id=user_id,
            deployment_id=deployment_db_id,
            flow_version_ids=flow_version_ids,
        )
        return {
            attachment.flow_version_id: str(attachment.provider_snapshot_id).strip()
            for attachment in attachments
            if isinstance(attachment.provider_snapshot_id, str) and attachment.provider_snapshot_id.strip()
        }

    async def _resolve_existing_tool_snapshot_ids(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        flow_version_ids: list[UUID],
    ) -> dict[UUID, str]:
        """Strict lookup: raises 422 if any flow_version_id is missing."""
        snapshot_map = await self._lookup_snapshot_ids(
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            db=db,
            flow_version_ids=flow_version_ids,
        )
        missing_flow_versions = [
            str(flow_version_id) for flow_version_id in flow_version_ids if flow_version_id not in snapshot_map
        ]
        if missing_flow_versions:
            msg = (
                "Cannot resolve provider snapshot ids for flow_version_ids in watsonx operations: "
                f"{missing_flow_versions}"
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        return snapshot_map
