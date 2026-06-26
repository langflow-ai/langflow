"""Watsonx Orchestrate deployment mapper implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentGetResult,
    DeploymentListLlmsResult,
    DeploymentListResult,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ExecutionStatusResult,
    ItemResult,
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
    CreateSnapshotBinding,
    CreateSnapshotBindings,
    FlowVersionPatch,
    ProviderSnapshotBinding,
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
    WatsonxApiDeploymentGetProviderData,
    WatsonxApiDeploymentListItemProviderData,
    WatsonxApiDeploymentListProviderData,
    WatsonxApiDeploymentLlmListResultData,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
    WatsonxApiExecutionInput,
    WatsonxApiProviderAccountCreate,
    WatsonxApiProviderAccountResponse,
    WatsonxApiProviderAccountUpdate,
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
    DeploymentListItem,
    DeploymentListResponse,
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentSnapshotListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    RunCreateResponse,
    RunStatusResponse,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    PAYLOAD_SCHEMAS as WXO_ADAPTER_PAYLOAD_SCHEMAS,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.utils import (
    check_provider_url_allowed,
    extract_tenant_from_url,
)
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    list_deployment_attachments_for_flow_version_ids,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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


class _FlowToolPayload(TypedDict):
    display_name: str
    provider_data: AdapterPayload
    raw_name: str


@register_mapper(AdapterType.DEPLOYMENT, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
class WatsonxOrchestrateDeploymentMapper(BaseDeploymentMapper):
    """Deployment mapper for Watsonx Orchestrate provider."""

    PROVIDER_LABEL = "watsonx Orchestrate"

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
        execution_input=PayloadSlot(
            adapter_model=WatsonxApiExecutionInput,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        deployment_llm_list_result=PayloadSlot(
            adapter_model=WatsonxApiDeploymentLlmListResultData,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
        provider_account_create=PayloadSlot(adapter_model=WatsonxApiProviderAccountCreate),
        provider_account_update=PayloadSlot(adapter_model=WatsonxApiProviderAccountUpdate),
        provider_account_response=PayloadSlot(
            adapter_model=WatsonxApiProviderAccountResponse,
            policy=PayloadSlotPolicy.VALIDATE_ONLY,
        ),
    )

    def _validate_create_provider_data(
        self,
        provider_data: dict[str, Any],
    ) -> tuple[WatsonxApiProviderAccountCreate, str]:
        """Parse, validate, and resolve tenant for create provider_data.

        Returns the parsed payload and the resolved tenant_id.
        Used by ``resolve_provider_account_create`` which needs the
        tenant_id for the DB model.
        """
        parsed = self._parse_and_check_url(provider_data)
        tenant_id = parsed.tenant_id
        if not tenant_id:
            tenant_id = extract_tenant_from_url(
                parsed.url,
                WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
            )
        if not tenant_id:
            msg = (
                "provider_data.tenant_id is required for watsonx-orchestrate provider accounts. "
                "Provide tenant_id explicitly or use a provider_data.url containing /instances/{tenant_id}."
            )
            raise ValueError(msg)
        return parsed, tenant_id

    def validate_create_provider_url(
        self,
        *,
        provider_data: dict[str, Any],
    ) -> str:
        return self._parse_and_check_url(provider_data).url

    def format_conflict_detail(
        self,
        raw_message: str,
        *,
        resource: str | None = None,
        resource_name: str | None = None,
    ) -> str:
        normalized_resource_name = str(resource_name or "").strip() or None
        if resource == "tool":
            return (
                f"A tool with name '{normalized_resource_name}' already exists in the provider. "
                "Please choose a different name."
                if normalized_resource_name
                else "A tool with this name already exists in the provider. Please choose a different name."
            )
        if resource == "connection":
            return (
                f"A connection with app_id '{normalized_resource_name}' already exists in the provider. "
                "Please choose a different name."
                if normalized_resource_name
                else "A connection referenced in this request already exists in the provider. "
                "Please choose a different name."
            )
        if resource == "agent":
            return (
                f"An agent with name '{normalized_resource_name}' already exists in the provider. "
                "Please choose a different name."
                if normalized_resource_name
                else "An agent with this name already exists in the provider. Please choose a different name."
            )

        return super().format_conflict_detail(
            raw_message,
            resource=resource,
            resource_name=resource_name,
        )

    def _parse_and_check_url(
        self,
        provider_data: dict[str, Any],
    ) -> WatsonxApiProviderAccountCreate:
        """Parse and validate provider_data for the create path.

        Validates schema, then checks the URL against the hostname allowlist.
        """
        parsed: WatsonxApiProviderAccountCreate = self.parse_api_request_slot(
            slot=self.api_payloads.provider_account_create,
            slot_name="provider_account_create",
            raw=provider_data,
        )
        check_provider_url_allowed(parsed.url, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
        return parsed

    async def resolve_execution_input(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        """Validate run provider_data and reject missing payloads at API boundary."""
        _ = db
        parsed: WatsonxApiExecutionInput = self.parse_api_request_slot(
            slot=self.api_payloads.execution_input,
            slot_name="execution_input",
            raw=raw,
        )
        return parsed.model_dump(mode="json", exclude_none=True)

    def resolve_load_from_provider_deployment_list_params(self) -> dict[str, Any] | None:
        """Force provider-backed list mode to draft agents only."""
        return {"environment": "draft"}

    def _parse_deployment_create_request(self, payload: DeploymentCreateRequest) -> WatsonxApiDeploymentCreatePayload:
        api_provider_payload: WatsonxApiDeploymentCreatePayload = self.parse_api_request_slot(
            slot=self.api_payloads.deployment_create,
            slot_name="deployment_create",
            raw=payload.provider_data,
            outer_payload=payload,
        )
        return api_provider_payload

    def resolve_deployment_model_for_create(
        self,
        *,
        result: DeploymentCreateResult,
        user_id: UUID,
        project_id: UUID,
        deployment_provider_account_id: UUID,
    ) -> Deployment:
        """Assemble the DB model for a wxO deployment create."""
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result,
            slot_name="deployment_create_result",
            raw=result.provider_result,
            operation="creating the deployment row in Langflow",
        )
        return Deployment(
            user_id=user_id,
            project_id=project_id,
            deployment_provider_account_id=deployment_provider_account_id,
            resource_key=str(result.id),
            display_name=adapter_provider_result.display_name,
            deployment_type=result.type,
            description=result.description,
        )

    def resolve_deployment_model_from_existing_resource_for_create(
        self,
        *,
        payload: DeploymentCreateRequest,
        existing_provider_resource: DeploymentGetResult,
        user_id: UUID,
        project_id: UUID,
        deployment_provider_account_id: UUID,
    ) -> Deployment:
        """Assemble the DB model for tracking an existing wxO agent."""
        existing_provider_data = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
            slot_name="deployment_item_data",
            raw=existing_provider_resource.provider_data,
            operation="reading deployment metadata from provider when attempting to track the resource in Langflow",
        )
        return Deployment(
            user_id=user_id,
            project_id=project_id,
            deployment_provider_account_id=deployment_provider_account_id,
            resource_key=str(existing_provider_resource.id),
            display_name=existing_provider_data.display_name,
            deployment_type=payload.type,
            description=existing_provider_data.description,
        )

    def resolve_kwargs_for_metadata_update(self, result: DeploymentUpdateResult) -> dict[str, Any]:
        """Assemble Deployment metadata update kwargs from the wxO update result."""
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            operation="syncing deployment metadata after update",
        )
        return {
            "display_name": adapter_provider_result.display_name,
            "description": adapter_provider_result.description,
        }

    def resolve_credentials(
        self,
        *,
        provider_data: dict[str, Any],
    ) -> dict[str, Any]:
        parsed: WatsonxApiProviderAccountUpdate = self.parse_api_request_slot(
            slot=self.api_payloads.provider_account_update,
            slot_name="provider_account_update",
            raw=provider_data,
        )
        return parsed.model_dump()

    def resolve_provider_account_create(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
        user_id: UUID,
    ) -> DeploymentProviderAccount:
        """Assemble provider-account DB model for create.

        The returned model carries a **plaintext** ``api_key``.  The CRUD
        layer (``create_provider_account_from_model``) encrypts it before
        persistence.
        """
        parsed, tenant_id = self._validate_create_provider_data(payload.provider_data)
        return DeploymentProviderAccount(
            user_id=user_id,
            name=payload.name,
            provider_tenant_id=tenant_id,
            provider_key=payload.provider_key,
            provider_url=parsed.url,
            api_key=parsed.api_key,
        )

    def resolve_provider_account_provider_data(
        self,
        provider_account: DeploymentProviderAccount,
    ) -> dict[str, Any] | None:
        parsed = self.parse_adapter_slot(
            slot=self.api_payloads.provider_account_response,
            slot_name="provider_account_response",
            raw={
                "url": provider_account.provider_url,
                "tenant_id": provider_account.provider_tenant_id,
            },
            operation="building the provider account response",
        )
        return parsed.model_dump(mode="json", exclude_none=True)

    def resolve_verify_credentials_for_create(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
    ) -> VerifyCredentials:
        parsed = self._parse_and_check_url(payload.provider_data)
        return VerifyCredentials(
            base_url=parsed.url,
            provider_data={"api_key": parsed.api_key},
        )

    def resolve_verify_credentials_for_update(
        self,
        *,
        payload: DeploymentProviderAccountUpdateRequest,
        existing_account: DeploymentProviderAccount,
    ) -> VerifyCredentials | None:
        if "provider_data" not in payload.model_fields_set:
            return None

        parsed: WatsonxApiProviderAccountUpdate = self.parse_api_request_slot(
            slot=self.api_payloads.provider_account_update,
            slot_name="provider_account_update",
            raw=payload.provider_data,
        )

        return VerifyCredentials(
            base_url=existing_account.provider_url,
            provider_data={"api_key": parsed.api_key},
        )

    def _build_flow_tool_payload(
        self,
        *,
        project_id: UUID,
        flow_version_id: UUID,
        tool_display_name: str,
    ) -> _FlowToolPayload:
        parsed_provider_data = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.flow_artifact,
            slot_name="flow_artifact",
            raw={
                "source_ref": str(flow_version_id),
                "project_id": str(project_id),
                "tool_display_name": tool_display_name,
            },
            operation="building flow tool provider data",
        )
        provider_data = parsed_provider_data.model_dump(mode="json", exclude_none=True)

        try:
            technical_name = provider_data["tool_name"]
        except KeyError as exc:
            msg = f"Unable to create tool name for flow_version_id: [{flow_version_id}]"
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc
        return {
            "display_name": tool_display_name,
            "provider_data": provider_data,
            "raw_name": technical_name,
        }

    def _get_flow_tool_payload(
        self,
        *,
        flow_tool_by_flow_version_id: dict[UUID, _FlowToolPayload],
        flow_version_id: UUID,
        field_name: str,
    ) -> _FlowToolPayload:
        try:
            return flow_tool_by_flow_version_id[flow_version_id]
        except KeyError as exc:
            msg = f"Failed to resolve wxO tool payload for {field_name}: [{flow_version_id}]"
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc

    def _build_deployment_create_adapter_payload(
        self,
        *,
        api_provider_payload: WatsonxApiDeploymentCreatePayload,
        flow_artifacts: list[tuple[UUID, Any]],
        flow_tool_by_flow_version_id: dict[UUID, _FlowToolPayload],
        provider_operations: list[AdapterPayload],
    ) -> AdapterPayload:
        return self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create,
            slot_name="deployment_create",
            raw=self._build_provider_payload_body(
                llm=api_provider_payload.llm,
                display_name=api_provider_payload.display_name,
                model_fields_set=api_provider_payload.model_fields_set,
                raw_tool_payloads=[
                    artifact.model_copy(
                        update={
                            "provider_data": flow_tool_by_flow_version_id[flow_version_id]["provider_data"],
                        }
                    ).model_dump(exclude_none=True)
                    for flow_version_id, artifact in flow_artifacts
                ],
                connections=api_provider_payload.connections,
                operations=provider_operations,
            ),
            operation="building the deployment_create provider payload",
        ).model_dump(mode="json")

    def _build_deployment_update_adapter_payload(
        self,
        *,
        api_provider_payload: WatsonxApiDeploymentUpdatePayload,
        raw_payloads: list[Any],
        provider_operations: list[AdapterPayload],
    ) -> AdapterPayload:
        return self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update,
            slot_name="deployment_update",
            raw=self._build_provider_payload_body(
                llm=api_provider_payload.llm,
                display_name=api_provider_payload.display_name,
                model_fields_set=api_provider_payload.model_fields_set,
                raw_tool_payloads=[artifact.model_dump(exclude_none=True) for artifact in raw_payloads],
                connections=api_provider_payload.connections,
                operations=provider_operations,
            ),
            operation="building the deployment_update provider payload",
        ).model_dump(mode="json", exclude_unset=True)

    def util_create_flow_version_ids(self, payload: DeploymentCreateRequest) -> list[UUID]:
        if "provider_data" not in payload.model_fields_set:
            # The create route uses this before provider creation to validate
            # referenced flow versions. Omitted provider_data means no
            # create-time flow attachments to validate; explicitly provided
            # provider_data must still satisfy the wxO create schema.
            return []

        api_provider_payload = self._parse_deployment_create_request(payload)
        return list(dict.fromkeys(item.flow_version_id for item in api_provider_payload.add_flows))

    def util_existing_deployment_resource_key_for_create(
        self,
        payload: DeploymentCreateRequest,
    ) -> str | None:
        if "provider_data" not in payload.model_fields_set:
            # The create route uses None to mean "create a new provider
            # resource" when provider_data is omitted. Explicit provider_data
            # must still satisfy the wxO create schema before we inspect it.
            return None

        api_provider_payload = self._parse_deployment_create_request(payload)
        return api_provider_payload.existing_agent_id

    def util_create_result_from_existing_resource(
        self,
        *,
        existing_resource: DeploymentGetResult,
    ) -> DeploymentCreateResult:
        """Build a create-style result payload for tracking an existing wxO agent.

        This path is used when create request includes ``existing_agent_id``
        without create-time mutation operations. ``created_*`` fields represent
        what this request created, so they are intentionally empty here.
        """
        existing_provider_data = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
            slot_name="deployment_item_data",
            raw=existing_resource.provider_data,
            operation="reading deployment metadata",
        )
        create_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result,
            slot_name="deployment_create_result",
            raw={
                "display_name": existing_provider_data.display_name,
                "app_ids": [],
                "tools_with_refs": [],
            },
            operation="building the create response for the existing resource",
        )
        return DeploymentCreateResult(
            id=existing_resource.id,
            type=existing_resource.type,
            name=existing_resource.name,
            description=existing_provider_data.description,
            provider_result=create_provider_result.model_dump(mode="json"),
        )

    async def _resolve_provider_payload_from_create_api(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        api_provider_payload: WatsonxApiDeploymentCreatePayload,
    ) -> AdapterPayload:
        flow_version_ids = list(dict.fromkeys(item.flow_version_id for item in api_provider_payload.add_flows))
        flow_artifacts = await build_project_scoped_flow_artifacts_from_flow_versions(
            db=db,
            user_id=user_id,
            project_id=project_id,
            reference_ids=flow_version_ids,
        )
        # Start with flow names as display labels, then let user-provided
        # tool_display_name overrides replace them. The adapter provider-data
        # schema generates the wxO technical tool name once; raw payload names
        # and bind operation selectors both reuse that generated value.
        tool_display_name_by_flow_version_id: dict[UUID, str] = {
            flow_version_id: artifact.name for flow_version_id, artifact in flow_artifacts
        }
        for item in api_provider_payload.add_flows:
            if not item.tool_display_name:
                continue
            tool_display_name_by_flow_version_id[item.flow_version_id] = item.tool_display_name
        flow_tool_by_flow_version_id = {
            flow_version_id: self._build_flow_tool_payload(
                project_id=project_id,
                flow_version_id=flow_version_id,
                tool_display_name=tool_display_name,
            )
            for flow_version_id, tool_display_name in tool_display_name_by_flow_version_id.items()
        }
        provider_operations = self._build_provider_operations(
            add_flows=api_provider_payload.add_flows,
            upsert_tools=api_provider_payload.upsert_tools,
            flow_tool_by_flow_version_id=flow_tool_by_flow_version_id,
        )
        return self._build_deployment_create_adapter_payload(
            api_provider_payload=api_provider_payload,
            flow_artifacts=flow_artifacts,
            flow_tool_by_flow_version_id=flow_tool_by_flow_version_id,
            provider_operations=provider_operations,
        )

    async def resolve_deployment_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentCreate:
        api_provider_payload = self._parse_deployment_create_request(payload)
        if api_provider_payload.llm is None:
            msg = "provider_data.llm is required for wxO deployment create."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        provider_payload = await self._resolve_provider_payload_from_create_api(
            user_id=user_id,
            project_id=project_id,
            db=db,
            api_provider_payload=api_provider_payload,
        )
        if api_provider_payload.display_name is None:
            msg = "provider_data.display_name is required for wxO deployment create."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        return AdapterDeploymentCreate(
            spec=BaseDeploymentData(
                description=payload.description,
                type=payload.type,
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
        description = payload.description
        has_description = "description" in payload.model_fields_set
        if "provider_data" not in payload.model_fields_set:
            # Metadata-only updates still need an adapter update for the spec,
            # but should not fabricate an empty wxO operations payload. If
            # provider_data is explicit, the wxO update schema owns validation.
            return AdapterDeploymentUpdate(spec=BaseDeploymentDataUpdate(description=description))

        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self.parse_api_request_slot(
            slot=self.api_payloads.deployment_update,
            slot_name="deployment_update",
            raw=payload.provider_data,
        )
        spec_kwargs: dict[str, Any] = {}
        if has_description:
            spec_kwargs["description"] = description
        adapter_spec = BaseDeploymentDataUpdate(**spec_kwargs) if spec_kwargs else None
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
        # Start with flow names as display labels, then let user-provided
        # tool_display_name overrides replace them. The adapter provider-data
        # schema generates the wxO technical tool name once; raw payload names
        # and bind operation selectors both reuse that generated value.
        tool_display_name_by_flow_version_id: dict[UUID, str] = {
            flow_version_id: artifact.name for flow_version_id, _version_number, _project_id, artifact in flow_artifacts
        }
        for item in api_provider_payload.upsert_flows:
            if not item.tool_display_name:
                continue
            if item.flow_version_id not in tool_display_name_by_flow_version_id:
                continue
            tool_display_name_by_flow_version_id[item.flow_version_id] = item.tool_display_name
        flow_tool_by_flow_version_id = {
            flow_version_id: self._build_flow_tool_payload(
                project_id=artifact_project_id,
                flow_version_id=flow_version_id,
                tool_display_name=tool_display_name_by_flow_version_id[flow_version_id],
            )
            for flow_version_id, _version_number, artifact_project_id, _artifact in flow_artifacts
        }
        raw_payloads = [
            artifact.model_copy(
                update={
                    "provider_data": flow_tool_by_flow_version_id[flow_version_id]["provider_data"],
                }
            )
            for flow_version_id, _version_number, _project_id, artifact in flow_artifacts
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
            flow_tool_by_flow_version_id=flow_tool_by_flow_version_id,
            flow_version_snapshot_id_map=flow_version_snapshot_id_map,
        )

        provider_payload = self._build_deployment_update_adapter_payload(
            api_provider_payload=api_provider_payload,
            raw_payloads=filtered_raw_payloads,
            provider_operations=provider_operations,
        )
        return AdapterDeploymentUpdate(
            spec=adapter_spec,
            provider_data=provider_payload,
        )

    def extract_snapshot_bindings(self, provider_view) -> list[ProviderSnapshotBinding]:
        bindings: list[ProviderSnapshotBinding] = []
        for item in provider_view.deployments:
            resource_key = str(item.id)

            item_provider_data = self.parse_adapter_slot(
                slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
                slot_name="deployment_item_data",
                raw=item.provider_data,
                operation="reading deployment list item metadata",
            )
            bindings.extend(
                ProviderSnapshotBinding(resource_key=resource_key, snapshot_id=str(snapshot_id))
                for snapshot_id in item_provider_data.tool_ids
            )
        return bindings

    def extract_list_item_provider_data(
        self,
        provider_view: DeploymentListResult,
    ) -> dict[str, dict[str, Any]]:
        provider_data_by_resource_key: dict[str, dict[str, Any]] = {}
        for item in provider_view.deployments:
            item_provider_data = self.parse_adapter_slot(
                slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
                slot_name="deployment_item_data",
                raw=item.provider_data,
                operation="reading deployment list item metadata",
            )

            resource_key = str(item.id)
            provider_data_by_resource_key[resource_key] = WatsonxApiDeploymentListItemProviderData(
                name=item.name,
                display_name=item_provider_data.display_name,
                llm=item_provider_data.llm,
                environments=item_provider_data.environments,
            ).model_dump(mode="json")

        return provider_data_by_resource_key

    def extract_metadata_for_list(
        self,
        provider_view: DeploymentListResult,
    ) -> dict[str, dict[str, Any]]:
        metadata_by_resource_key: dict[str, dict[str, Any]] = {}
        for item in provider_view.deployments:
            item_provider_data = self.parse_adapter_slot(
                slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
                slot_name="deployment_item_data",
                raw=item.provider_data,
                operation="reading deployment list item metadata",
            )
            resource_key = str(item.id)
            metadata_by_resource_key[resource_key] = {
                "display_name": item_provider_data.display_name,
                "description": item_provider_data.description,
            }
        return metadata_by_resource_key

    def extract_snapshot_bindings_for_get(
        self,
        get_result: DeploymentGetResult,
        *,
        resource_key: str,
    ) -> list[ProviderSnapshotBinding]:
        if get_result.provider_data is None:
            msg = "An internal error occured. provider_data is required from wxO adapter for get()."
            raise ValueError(msg)
        if "tool_ids" not in get_result.provider_data:
            msg = "An internal error occured. provider_data must contain 'tool_ids' from wxO adapter for get()."
            raise ValueError(msg)

        tool_ids = get_result.provider_data["tool_ids"]

        if not isinstance(tool_ids, list):
            msg = "An internal error occured. provider_data['tool_ids'] must be a list from wxO adapter for get()."
            raise ValueError(msg)  # noqa: TRY004

        return [
            ProviderSnapshotBinding(resource_key=resource_key, snapshot_id=str(snapshot_id)) for snapshot_id in tool_ids
        ]

    def extract_metadata_for_get(
        self,
        get_result: DeploymentGetResult,
    ) -> dict[str, Any]:
        parsed = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
            slot_name="deployment_item_data",
            raw=get_result.provider_data,
            operation="reading deployment metadata",
        )
        return {
            "display_name": parsed.display_name,
            "description": parsed.description,
        }

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
        restores deployment display_name and description via spec.

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
        # TODO: Reintroduce a non-unique Deployment.name column for provider technical names
        # and include it here so rollback can restore wxO `name` from Langflow's stored metadata.
        provider_payload = update_slot.apply(
            {
                "put_tools": existing_tool_ids,
                "display_name": deployment.display_name,
            }
        )
        rollback_description = (
            deployment.description if deployment.description and deployment.description.strip() else None
        )

        return AdapterDeploymentUpdate(
            spec=BaseDeploymentDataUpdate(
                description=rollback_description,
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
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_create_result,
            slot_name="deployment_create_result",
            raw=result.provider_result,
            operation="creating the deployment",
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
            name=result.name,
            display_name=deployment_row.display_name,
            created_app_ids=list(adapter_provider_result.app_ids),
            created_tools=created_tools,
        )
        return DeploymentCreateResponse(
            id=deployment_row.id,
            provider_id=deployment_row.deployment_provider_account_id,
            provider_key=provider_key,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            resource_key=deployment_row.resource_key,
            provider_data=provider_api_result.model_dump(mode="json"),
        )

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
        *,
        provider_key: str,
    ) -> DeploymentUpdateResponse:
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_update_result,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            operation="updating the deployment",
        )
        created_tools = self._to_api_created_tools(
            adapter_created_snapshot_bindings=adapter_provider_result.created_snapshot_bindings
        )
        provider_api_result = WatsonxApiDeploymentUpdateResultData(
            name=adapter_provider_result.name,
            display_name=adapter_provider_result.display_name,
            created_app_ids=list(adapter_provider_result.created_app_ids),
            created_tools=created_tools,
        )
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            provider_id=deployment_row.deployment_provider_account_id,
            provider_key=provider_key,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            resource_key=deployment_row.resource_key,
            provider_data=provider_api_result.model_dump(mode="json"),
        )

    def shape_llm_list_result(self, result: DeploymentListLlmsResult) -> DeploymentLlmListResponse:
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_llm_list_result,
            slot_name="deployment_llm_list_result",
            raw=result.provider_result,
            operation="listing available models",
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
        parsed = self.parse_adapter_slot(
            slot=slot,
            slot_name="deployment_create_result",
            raw=result.provider_result,
            operation="creating the deployment",
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
        parsed = self.parse_adapter_slot(
            slot=slot,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            operation="updating the deployment",
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
        parsed = self.parse_adapter_slot(
            slot=slot,
            slot_name="deployment_update_result",
            raw=result.provider_result,
            operation="updating the deployment",
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
        if "provider_data" not in payload.model_fields_set:
            # The update route uses this patch to reconcile DB attachments after
            # provider mutation. Metadata-only updates have no attachment delta;
            # explicit provider_data must still satisfy the wxO update schema.
            return FlowVersionPatch()

        api_provider_payload: WatsonxApiDeploymentUpdatePayload = self.parse_api_request_slot(
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
    ) -> RunCreateResponse:
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.execution_create_result,
            slot_name="execution_create_result",
            raw=result.provider_result,
            operation="starting the execution",
        )
        api_provider_result = WatsonxApiAgentExecutionCreateResultData(
            id=adapter_provider_result.execution_id,
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
        return RunCreateResponse(
            deployment_id=deployment_id,
            provider_data=api_provider_result.model_dump(),
            # includes None intentionally, simply passes through
            # wxo api response, which can contain null values
        )

    def shape_execution_status_result(
        self,
        result: ExecutionStatusResult,
        *,
        deployment_id: UUID,
    ) -> RunStatusResponse:
        adapter_provider_result = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.execution_status_result,
            slot_name="execution_status_result",
            raw=result.provider_result,
            operation="checking execution status",
        )
        api_provider_result = WatsonxApiAgentExecutionStatusResultData(
            id=adapter_provider_result.execution_id,
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
        return RunStatusResponse(
            deployment_id=deployment_id,
            provider_data=api_provider_result.model_dump(),
            # includes None intentionally, simply passes through
            # wxo api response, which can contain null values
        )

    def shape_deployment_list_result(
        self,
        result: DeploymentListResult,
    ) -> DeploymentListResponse:
        provider_result = {
            "deployments": [self._shape_provider_deployment_list_entry(item) for item in result.deployments]
        }
        validated_payload = self.parse_adapter_slot(
            slot=self.api_payloads.deployment_list_result,
            slot_name="deployment_list_result",
            raw=provider_result,
            operation="building deployment list provider payload",
        )
        return DeploymentListResponse(
            deployments=None,
            provider_data=validated_payload.model_dump(mode="json"),
        )

    def shape_deployment_list_items(
        self,
        *,
        rows_with_counts: list[tuple[Any, int, list[tuple[UUID, str | None]]]],
        has_flow_filter: bool = False,
        provider_key: str,
        provider_data_by_resource_key: dict[str, dict[str, Any]] | None = None,
    ) -> list[DeploymentListItem]:
        if provider_data_by_resource_key is None:
            msg = "provider_data_by_resource_key is required from wxO list sync."
            raise ValueError(msg)

        items: list[DeploymentListItem] = []
        for row, attached_count, matched_attachments in rows_with_counts:
            provider_data = provider_data_by_resource_key.get(row.resource_key)
            if provider_data is None:
                msg = f"Missing provider_data for wxO deployment resource_key={row.resource_key!r}."
                raise ValueError(msg)
            items.append(
                DeploymentListItem(
                    id=row.id,
                    provider_id=row.deployment_provider_account_id,
                    provider_key=provider_key,
                    resource_key=row.resource_key,
                    type=row.deployment_type,
                    description=row.description,
                    attached_count=attached_count,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    flow_version_ids=[fv_id for fv_id, _ in matched_attachments] if has_flow_filter else None,
                    provider_data=provider_data,
                )
            )
        return items

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

        return DeploymentConfigListResponse(provider_data=validated_payload)

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
            display_name = item_provider_data.get("display_name")
            items_all.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "display_name": display_name,
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

        return DeploymentSnapshotListResponse(provider_data=validated_payload)

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
        flow_version_item_data_by_snapshot_id = self._resolve_flow_version_item_data_by_snapshot_id(
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
                provider_data=flow_version_item_data_by_snapshot_id.get(row.snapshot_id),
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

    def _resolve_flow_version_item_data_by_snapshot_id(
        self,
        *,
        snapshot_result: SnapshotListResult | None,
    ) -> dict[str, dict[str, Any]]:
        """Build API flow-version item provider_data keyed by snapshot id."""
        if snapshot_result is None:
            return {}
        if not snapshot_result.snapshots:
            return {}

        item_data_by_snapshot_id: dict[str, dict[str, Any]] = {}
        for snapshot in snapshot_result.snapshots:
            snapshot_id = str(snapshot.id).strip()
            if not snapshot_id:
                msg = "Invalid flow-version provider_data payload: snapshot id must be a non-empty string."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)

            provider_data = snapshot.provider_data

            if not isinstance(provider_data, dict) or not provider_data:
                msg = "Invalid flow-version provider_data payload: snapshot provider_data must be a non-empty object."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)

            raw_connections = provider_data.get("connections")
            if not isinstance(raw_connections, dict):
                msg = "Invalid flow-version provider_data payload: connections must be a dict."
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
            try:
                item_data_by_snapshot_id[snapshot_id] = self._validate_slot(
                    self.api_payloads.deployment_item_data,
                    {
                        "app_ids": list(raw_connections.keys()),
                        "tool_name": snapshot.name,
                        "tool_display_name": provider_data["display_name"],
                    },
                )
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load tool data for tool id {snapshot_id}",
                ) from exc
            except AdapterPayloadValidationError as exc:
                detail = exc.format_first_error()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Invalid flow-version provider_data payload: {detail}",
                ) from exc

        return item_data_by_snapshot_id

    def _shape_provider_deployment_list_entry(self, item: ItemResult) -> dict[str, Any]:
        item_provider_data = item.provider_data
        if not isinstance(item_provider_data, dict):
            msg = "Invalid deployment list item provider_data payload: expected object."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return {
            **item_provider_data,
            "id": str(item.id),
            "name": item.name,
            "type": item.type,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def shape_deployment_get_data(
        self,
        provider_data: AdapterPayload | None,
        *,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        parsed = self.parse_adapter_slot(
            slot=WXO_ADAPTER_PAYLOAD_SCHEMAS.deployment_item_data,
            slot_name="deployment_item_data",
            raw=provider_data,
            operation="reading deployment metadata",
        )
        if name is None:
            msg = "Missing deployment name while shaping wxO deployment metadata."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return WatsonxApiDeploymentGetProviderData(
            llm=parsed.llm,
            name=name,
            display_name=parsed.display_name,
            environments=parsed.environments,
        ).model_dump(mode="json")

    def shape_config_item_data(self, provider_data: dict[str, Any]) -> WatsonxApiConfigListItem:
        return self.parse_adapter_slot(
            slot=self.api_payloads.config_item_data,
            slot_name="config_item_data",
            raw=provider_data,
            operation="reading the configuration",
        )

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
        flow_tool_by_flow_version_id: dict[UUID, _FlowToolPayload],
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

            flow_tool = self._get_flow_tool_payload(
                flow_tool_by_flow_version_id=flow_tool_by_flow_version_id,
                flow_version_id=flow_version_id,
                field_name="add_flows item flow_version_id",
            )
            if not item.app_ids:
                # Raw tool is still created via tools.raw_payloads;
                # no provider bind operation needed.
                continue
            provider_operations.append(
                self._to_bind_provider_operation(
                    raw_name=flow_tool["raw_name"],
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
                if item.tool_display_name:
                    provider_operations.append(
                        {
                            "op": "rename_tool",
                            "tool": {
                                "source_ref": str(flow_version_id),
                                "tool_id": existing_tool_id,
                            },
                            "tool_display_name": item.tool_display_name,
                        }
                    )
                continue

            if item.remove_app_ids:
                msg = (
                    "Cannot resolve provider snapshot ids for flow_version_ids "
                    f"in watsonx operations: [{flow_version_id}]"
                )
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
            flow_tool = self._get_flow_tool_payload(
                flow_tool_by_flow_version_id=flow_tool_by_flow_version_id,
                flow_version_id=flow_version_id,
                field_name="upsert_flows item flow_version_id",
            )
            if item.add_app_ids:
                provider_operations.append(
                    self._to_bind_provider_operation(
                        raw_name=flow_tool["raw_name"],
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
        display_name: str | None,
        model_fields_set: set[str],
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
        if "llm" in model_fields_set:
            payload["llm"] = llm
        if "display_name" in model_fields_set:
            payload["display_name"] = display_name
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
