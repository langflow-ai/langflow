# ruff: noqa: ARG002
"""Base deployment payload mapper contracts for API <-> adapter transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from lfx.services.adapters.deployment.payloads import DeploymentPayloadFields
from lfx.services.adapters.deployment.schema import (
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentCreateResult,
    DeploymentUpdateResult,
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    SnapshotItems,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreate as AdapterDeploymentCreate,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.adapters.payload import PayloadSlot

from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    ExecutionCreateRequest,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
)

from .contracts import (
    CreatedSnapshotIds,
    CreateFlowArtifactProviderData,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBindings,
)
from .helpers import build_project_scoped_flow_artifacts_from_flow_versions

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount


@dataclass(frozen=True)
class DeploymentApiPayloads(DeploymentPayloadFields):
    """API-side payload schema registry for deployment providers.

    Ownership boundary:
    Langflow owns API slot population here because API payloads may include
    Langflow-specific references and reshaping requirements. Adapter-side
    slot population is defined separately via ``DeploymentPayloadSchemas``.
    """


class BaseDeploymentMapper:
    """Per-provider mapper for deployment API payloads.

    Mapper vs adapter responsibilities:
    - Mapper: API-boundary translation/validation (Langflow schemas <-> adapter payloads).
    - Adapter: provider execution (network calls, provider semantics, side effects).

    Selection contract:
    The mapper is resolved using the same ``(AdapterType, provider_key)``
    coordinates used for adapter resolution, so both layers stay aligned for
    a request.

    The base implementation is intentionally passthrough-first:
    - inbound ``resolve_*`` methods normalize API requests into adapter input
      contracts. Dict payloads are returned unchanged unless an API payload
      slot is configured for that field, in which case slot ``apply`` is used.
    - outbound ``shape_*`` methods normalize adapter results into API response
      contracts where applicable (for example deployment update and execution
      responses), while payload-only shapers return provider dicts unchanged.

    Provider-specific mappers override only the methods that need
    Langflow-aware resolution or payload reshaping.
    """

    api_payloads: ClassVar[DeploymentApiPayloads] = DeploymentApiPayloads()

    async def resolve_deployment_spec(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_spec, raw)

    async def resolve_deployment_config(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_config, raw)

    async def resolve_deployment_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentCreate:
        snapshot_payloads: list[BaseFlowArtifact] | None = None
        if payload.flow_version_ids:
            flow_artifacts = await build_project_scoped_flow_artifacts_from_flow_versions(
                reference_ids=payload.flow_version_ids,
                user_id=user_id,
                project_id=project_id,
                db=db,
            )
            snapshot_payloads = [
                artifact.model_copy(
                    update={
                        "provider_data": self.util_create_flow_artifact_provider_data(
                            project_id=project_id,
                            flow_version_id=flow_version_id,
                        ).model_dump(exclude_none=True),
                    }
                )
                for flow_version_id, artifact in flow_artifacts
            ]
        adapter_snapshot = SnapshotItems(raw_payloads=snapshot_payloads) if snapshot_payloads else None
        adapter_config = (
            ConfigItem(reference_id=payload.config.reference_id)
            if payload.config is not None and payload.config.reference_id is not None
            else ConfigItem(raw_payload=payload.config.raw_payload)
            if payload.config is not None
            else None
        )
        provider_data = self._validate_slot(self.api_payloads.deployment_create, payload.provider_data)
        return AdapterDeploymentCreate(
            spec=payload.spec,
            snapshot=adapter_snapshot,
            config=adapter_config,
            provider_data=provider_data,
        )

    async def resolve_deployment_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        payload: DeploymentUpdateRequest,
    ) -> AdapterDeploymentUpdate:
        _ = (user_id, deployment_db_id)
        adapter_config = (
            ConfigDeploymentBindingUpdate(**payload.config.model_dump(exclude_unset=True))
            if payload.config is not None
            else None
        )
        provider_data = self._validate_slot(self.api_payloads.deployment_update, payload.provider_data)
        return AdapterDeploymentUpdate(
            spec=payload.spec,
            config=adapter_config,
            provider_data=provider_data,
        )

    async def resolve_execution_input(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.execution_input, raw)

    async def resolve_execution_create(
        self,
        *,
        deployment_resource_key: str,
        db: AsyncSession,
        payload: ExecutionCreateRequest,
    ) -> ExecutionCreate:
        return ExecutionCreate(
            deployment_id=deployment_resource_key,
            provider_data=await self.resolve_execution_input(payload.provider_data, db),
        )

    async def resolve_deployment_list_params(
        self, raw: dict[str, Any] | None, db: AsyncSession
    ) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_list_params, raw)

    async def resolve_config_list_params(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.config_list_params, raw)

    async def resolve_snapshot_list_params(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.snapshot_list_params, raw)

    def shape_deployment_create_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
    ) -> DeploymentUpdateResponse:
        provider_data = result.provider_result if isinstance(result.provider_result, dict) else None
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            name=deployment_row.name,
            description=deployment_row.description,
            type=deployment_row.deployment_type,
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            provider_data=provider_data,
        )

    def resolve_provider_tenant_id(self, *, provider_url: str, provider_tenant_id: str | None) -> str | None:
        """Resolve provider tenant id for provider-account create/update."""
        _ = provider_url
        return provider_tenant_id

    def shape_provider_account_response(
        self,
        provider_account: DeploymentProviderAccount,
    ) -> DeploymentProviderAccountGetResponse:
        return DeploymentProviderAccountGetResponse(
            id=provider_account.id,
            provider_tenant_id=provider_account.provider_tenant_id,
            provider_key=provider_account.provider_key,
            provider_url=provider_account.provider_url,
            created_at=provider_account.created_at,
            updated_at=provider_account.updated_at,
        )

    def util_create_flow_artifact_provider_data(
        self,
        *,
        project_id: UUID,
        flow_version_id: UUID,
    ) -> CreateFlowArtifactProviderData:
        """Build provider_data for create-time flow artifacts.

        Contract schema: ``CreateFlowArtifactProviderData``.
        """
        _ = project_id
        return CreateFlowArtifactProviderData(source_ref=str(flow_version_id))

    def util_create_flow_version_ids(self, payload: DeploymentCreateRequest) -> list[UUID]:
        """Resolve flow-version ids referenced by create payload."""
        return list(payload.flow_version_ids or [])

    def util_create_snapshot_bindings(
        self,
        *,
        result: DeploymentCreateResult,
    ) -> CreateSnapshotBindings:
        """Reconcile normalized create bindings as ``source_ref -> snapshot_id``.

        Base behavior is intentionally empty because binding extraction is
        adapter-result-schema-specific and must be implemented by provider
        mappers that define create-time snapshot association contracts.
        """
        _ = result
        return CreateSnapshotBindings()

    def util_created_snapshot_ids(
        self,
        *,
        result: DeploymentUpdateResult,
    ) -> CreatedSnapshotIds:
        """Reconcile created snapshot ids for attachment patching.

        Contract schema: ``CreatedSnapshotIds``.
        """
        _ = result
        return CreatedSnapshotIds()

    def util_update_snapshot_bindings(
        self,
        *,
        result: DeploymentUpdateResult,
    ) -> UpdateSnapshotBindings:
        """Reconcile update-time ``source_ref -> snapshot_id`` bindings.

        Base behavior is intentionally empty because binding extraction is
        adapter-result-schema-specific and must be implemented by provider
        mappers that define update-time snapshot association contracts.
        """
        _ = result
        return UpdateSnapshotBindings()

    def util_flow_version_patch(self, payload: DeploymentUpdateRequest) -> FlowVersionPatch:
        """Reconcile attachment patch operation from update payload.

        Contract schema: ``FlowVersionPatch``.
        """
        return FlowVersionPatch(
            add_flow_version_ids=list(payload.add_flow_version_ids or []),
            remove_flow_version_ids=list(payload.remove_flow_version_ids or []),
        )

    def util_snapshot_ids_to_verify(
        self,
        attachments: list[Any],
    ) -> list[str]:
        """Extract provider snapshot IDs that should be verified against the provider.

        Called by read-path snapshot-level sync to determine which attachments
        carry a provider-trackable snapshot identity.  The route passes the
        returned IDs to the adapter's ``list_snapshots`` by-IDs mode and
        deletes DB rows whose IDs are no longer present on the provider.

        The base implementation returns an empty list, meaning snapshot-level
        sync is a no-op for providers that do not track snapshots separately.
        Provider mappers that assign ``provider_snapshot_id`` on attachments
        must override this to extract those IDs.
        """
        _ = attachments
        return []

    async def resolve_rollback_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        deployment_resource_key: str,
        db: AsyncSession,
    ) -> AdapterDeploymentUpdate | None:
        """Build a compensating update payload from current DB attachment state.

        Called when a provider update succeeded but the subsequent DB commit
        failed. The returned payload should restore the provider to match the
        (still-committed) DB state.

        Returns ``None`` when the mapper cannot construct a meaningful rollback,
        in which case provider state may diverge from the DB.
        """
        _ = (user_id, deployment_db_id, deployment_resource_key, db)
        return None

    def shape_deployment_operation_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_deployment_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_config_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_snapshot_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_execution_create_provider_data(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        """Shape provider_data for execution create responses."""
        return provider_result

    def shape_execution_status_provider_data(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        """Shape provider_data for execution status responses."""
        return provider_result

    def shape_execution_create_result(
        self,
        result: ExecutionCreateResult,
        *,
        deployment_id: UUID,
    ) -> ExecutionCreateResponse:
        provider_result = self.shape_execution_create_provider_data(
            result.provider_result if isinstance(result.provider_result, dict) else None
        )
        return ExecutionCreateResponse(
            execution_id=self.util_execution_id(
                execution_id=result.execution_id,
                provider_result=provider_result,
            ),
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def shape_execution_status_result(
        self,
        result: ExecutionStatusResult,
        *,
        deployment_id: UUID,
        fallback_execution_id: str | None = None,
    ) -> ExecutionStatusResponse:
        provider_result = self.shape_execution_status_provider_data(
            result.provider_result if isinstance(result.provider_result, dict) else None
        )
        return ExecutionStatusResponse(
            execution_id=self.util_execution_id(
                execution_id=result.execution_id or fallback_execution_id,
                provider_result=provider_result,
            ),
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def util_execution_id(
        self,
        *,
        execution_id: str | None,
        provider_result: dict[str, Any] | None,
    ) -> str | None:
        """Resolve execution identifier for API responses."""
        _ = provider_result
        return execution_id

    def util_execution_deployment_resource_key(
        self,
        *,
        deployment_id: str | None,
        provider_result: dict[str, Any] | None,
    ) -> str | None:
        """Resolve provider deployment resource key from execution result."""
        _ = provider_result
        return (deployment_id or "").strip() or None

    def shape_deployment_item_data(self, provider_data: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_data

    def shape_deployment_status_data(self, provider_data: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_data

    @staticmethod
    def _validate_slot(
        slot: PayloadSlot[Any] | None,
        raw: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Validate a payload dict against a configured API slot."""
        if raw is None or slot is None:
            return raw
        return slot.apply(raw)
