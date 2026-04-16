# ruff: noqa: ARG002
"""Base deployment payload mapper contracts for API <-> adapter transforms.

Provider-account credential contract
-------------------------------------
Provider credentials arrive in the API request as an opaque
``provider_data: dict`` and leave via two mapper methods:

* **API -> Adapter** (``resolve_verify_credentials_for_create``): packs the
  request's ``provider_data`` into the adapter-layer ``VerifyCredentials``
  model so the deployment adapter can validate the credentials against the
  provider.

* **API -> DB** (``resolve_credentials``): extracts credentials from
  ``provider_data`` and returns DB column-value pairs
  (e.g. ``{"api_key": "..."}``) used by mapper-owned create/update
  assembly methods.

The mapper is the **single** component that understands a provider's
credential shape.  The API schema treats ``provider_data`` as opaque and
the DB model keeps a fixed column set (currently ``api_key: str``).  If a
future provider requires a different storage layout (multiple columns, a
serialised JSON blob, etc.), only the mapper and CRUD layer need to evolve
-- the route and schema remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.payloads import DeploymentPayloadFields
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigListParams,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentListLlmsResult,
    DeploymentListResult,
    DeploymentUpdateResult,
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    SnapshotListParams,
    SnapshotListResult,
    VerifyCredentials,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreate as AdapterDeploymentCreate,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.adapters.payload import PayloadSlot

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
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentSnapshotListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
)

from .contracts import (
    CreatedSnapshotIds,
    CreateFlowArtifactProviderData,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBindings,
)
from .helpers import page_offset

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )


@dataclass(frozen=True)
class DeploymentApiPayloads(DeploymentPayloadFields):
    """API-side payload schema registry for deployment providers.

    Ownership boundary:
    Langflow owns API slot population here because API payloads may include
    Langflow-specific references and reshaping requirements. Adapter-side
    slot population is defined separately via ``DeploymentPayloadSchemas``.
    """

    provider_account_create: PayloadSlot | None = None
    provider_account_update: PayloadSlot | None = None
    provider_account_response: PayloadSlot | None = None


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
        _ = (user_id, project_id)
        provider_data = self._validate_slot(self.api_payloads.deployment_create, payload.provider_data)
        return AdapterDeploymentCreate(
            spec=BaseDeploymentData(
                name=payload.name,
                description=payload.description,
                type=payload.type,
            ),
            provider_data=provider_data,
        )

    async def resolve_deployment_update_for_existing_create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        payload: DeploymentCreateRequest,
    ) -> AdapterDeploymentUpdate:
        """Build adapter update payload for existing-resource create onboarding."""
        create_payload = await self.resolve_deployment_create(
            user_id=user_id,
            project_id=project_id,
            db=db,
            payload=payload,
        )
        return AdapterDeploymentUpdate(
            spec=BaseDeploymentDataUpdate(
                name=payload.name,
                description=payload.description,
            ),
            provider_data=create_payload.provider_data,
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
        adapter_spec = (
            BaseDeploymentDataUpdate(
                name=payload.name,
                description=payload.description,
            )
            if payload.name is not None or payload.description is not None
            else None
        )
        provider_data = self._validate_slot(self.api_payloads.deployment_update, payload.provider_data)
        return AdapterDeploymentUpdate(
            spec=adapter_spec,
            provider_data=provider_data,
        )

    async def resolve_execution_input(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.execution_input, raw)

    async def resolve_execution_create(
        self,
        *,
        deployment_resource_key: str,
        db: AsyncSession,
        payload: RunCreateRequest,
    ) -> ExecutionCreate:
        return ExecutionCreate(
            deployment_id=deployment_resource_key,
            provider_data=await self.resolve_execution_input(payload.provider_data, db),
        )

    async def resolve_deployment_list_params(
        self, raw: dict[str, Any] | None, db: AsyncSession
    ) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_list_params, raw)

    def resolve_load_from_provider_deployment_list_params(self) -> dict[str, Any] | None:
        """Return provider_params for provider-backed deployment listing.

        Default behavior applies no provider-specific filters.
        """
        return None

    async def resolve_config_list_params(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.config_list_params, raw)

    async def resolve_snapshot_list_params(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.snapshot_list_params, raw)

    def resolve_snapshot_update_artifact(
        self,
        *,
        flow_version: FlowVersion,
        flow_row: Flow | None,
        deployment: Deployment,
    ) -> BaseFlowArtifact:
        """Build a ``BaseFlowArtifact`` for a snapshot content update.

        The base implementation assembles the artifact from the flow version
        data and the parent flow's metadata.  Provider-specific mappers
        override this to inject ``provider_data``.

        Raises ``HTTPException(422)`` when the artifact cannot be built
        (e.g. the parent flow has been deleted or the data is malformed).
        """
        from pydantic import ValidationError

        flow_name = getattr(flow_row, "name", None) or ""
        if not flow_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot build deployment artifact: the parent flow for version "
                    f"'{flow_version.id}' has been deleted or has no name."
                ),
            )
        try:
            return BaseFlowArtifact(
                id=flow_version.flow_id,
                name=flow_name,
                description=getattr(flow_row, "description", None),
                data=flow_version.data,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Flow version '{flow_version.id}' cannot be used as a deployment "
                    f"artifact: {exc.errors()[0]['msg']}"
                ),
            ) from exc

    async def resolve_config_list_adapter_params(
        self,
        *,
        deployment_resource_key: str | None,
        provider_params: dict[str, Any] | None,
        db: AsyncSession,
    ) -> ConfigListParams:
        resolved_provider_params = await self.resolve_config_list_params(provider_params, db)
        return ConfigListParams(
            deployment_ids=[deployment_resource_key] if deployment_resource_key is not None else None,
            provider_params=resolved_provider_params,
        )

    async def resolve_snapshot_list_adapter_params(
        self,
        *,
        deployment_resource_key: str | None,
        snapshot_names: list[str] | None = None,
        provider_params: dict[str, Any] | None,
        db: AsyncSession,
    ) -> SnapshotListParams:
        resolved_provider_params = await self.resolve_snapshot_list_params(provider_params, db)
        return SnapshotListParams(
            deployment_ids=[deployment_resource_key] if deployment_resource_key is not None else None,
            snapshot_names=snapshot_names or None,
            provider_params=resolved_provider_params,
        )

    def shape_deployment_list_items(
        self,
        *,
        rows_with_counts: list[tuple[Deployment, int, list[tuple[UUID, str | None]]]],
        has_flow_filter: bool = False,
        provider_key: str,
    ) -> list[DeploymentListItem]:
        return [
            DeploymentListItem(
                id=row.id,
                provider_id=row.deployment_provider_account_id,
                provider_key=provider_key,
                resource_key=row.resource_key,
                type=row.deployment_type,
                name=row.name,
                description=row.description,
                attached_count=attached_count,
                created_at=row.created_at,
                updated_at=row.updated_at,
                flow_version_ids=[fv_id for fv_id, _ in matched_attachments] if has_flow_filter else None,
            )
            for row, attached_count, matched_attachments in rows_with_counts
        ]

    def shape_flow_version_list_result(
        self,
        *,
        rows: list[tuple[FlowVersionDeploymentAttachment, FlowVersion, str | None]],
        snapshot_result: SnapshotListResult | None,
        page: int,
        size: int,
        total: int,
    ) -> DeploymentFlowVersionListResponse:
        _ = snapshot_result
        flow_versions = [
            DeploymentFlowVersionListItem(
                id=flow_version.id,
                flow_id=flow_version.flow_id,
                flow_name=flow_name,
                version_number=flow_version.version_number,
                attached_at=attachment.created_at,
                provider_snapshot_id=(attachment.provider_snapshot_id or "").strip() or None,
                provider_data=None,
            )
            for attachment, flow_version, flow_name in rows
        ]
        return DeploymentFlowVersionListResponse(
            flow_versions=flow_versions,
            page=page,
            size=size,
            total=total,
        )

    def shape_deployment_create_result(
        self,
        result: DeploymentCreateResult,
        deployment_row: Deployment,
        *,
        provider_key: str,
    ) -> DeploymentCreateResponse:
        provider_data = result.provider_result if isinstance(result.provider_result, dict) else None
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
            provider_data=provider_data,
        )

    def shape_deployment_update_result(
        self,
        result: DeploymentUpdateResult,
        deployment_row: Deployment,
        *,
        provider_key: str,
    ) -> DeploymentUpdateResponse:
        provider_data = result.provider_result if isinstance(result.provider_result, dict) else None
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
            provider_data=provider_data,
        )

    def validate_create_provider_url(
        self,
        *,
        provider_data: dict[str, Any],
    ) -> str:
        """Resolve and validate provider URL from create provider_data.

        Provider mappers must override this for provider-account create.
        """
        _ = provider_data
        raise NotImplementedError

    def format_conflict_detail(
        self,
        raw_message: str,
        *,
        resource: str | None = None,
        resource_name: str | None = None,
    ) -> str:
        """Format provider conflict errors for API responses.

        Provider-specific mappers may override this to map provider-native
        conflict wording to clearer end-user guidance.  Subclasses use
        *resource* and *resource_name* to produce targeted messages.
        """
        _ = raw_message, resource, resource_name
        return (
            "A resource conflict occurred in the deployment provider. The requested operation could not be completed."
        )

    def resolve_credentials(
        self,
        *,
        provider_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract credentials from provider_data and return DB column->value pairs.

        Provider mappers must override this.  The returned dict is spread into
        the CRUD layer's keyword arguments (e.g. ``{"api_key": "..."}`` today;
        a future provider could return multiple columns or a serialized JSON
        blob).
        """
        raise NotImplementedError

    def resolve_provider_account_create(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
        user_id: UUID,
    ) -> DeploymentProviderAccount:
        """Assemble provider-account DB model for create.

        Provider mappers must override this so provider-specific create
        semantics stay out of the base mapper.
        """
        _ = (payload, user_id)
        raise NotImplementedError

    def resolve_provider_account_update(
        self,
        *,
        payload: DeploymentProviderAccountUpdateRequest,
        existing_account: DeploymentProviderAccount,
    ) -> dict[str, Any]:
        """Assemble DB column-value kwargs for a provider-account update.

        Only fields present in ``payload.model_fields_set`` are included so
        the CRUD layer receives a minimal diff. Provider-account update fields
        are intentionally limited to mutable values (display name and
        credentials).
        """
        _ = existing_account
        update_kwargs: dict[str, Any] = {}
        if "name" in payload.model_fields_set:
            update_kwargs["name"] = payload.name
        if "provider_data" in payload.model_fields_set:
            if payload.provider_data is None:
                msg = "'provider_data' cannot be null when provided."
                raise ValueError(msg)
            update_kwargs.update(self.resolve_credentials(provider_data=payload.provider_data))
        return update_kwargs

    def resolve_verify_credentials_for_create(
        self,
        *,
        payload: DeploymentProviderAccountCreateRequest,
    ) -> VerifyCredentials:
        """Build adapter verify-credentials input from create payload.

        The base implementation extracts ``base_url`` from
        ``provider_data.url``. Credentials are provider-specific and must be
        packed into ``provider_data`` by provider mapper overrides.
        """
        _ = payload
        raise NotImplementedError

    def resolve_verify_credentials_for_update(
        self,
        *,
        payload: DeploymentProviderAccountUpdateRequest,
        existing_account: DeploymentProviderAccount,
    ) -> VerifyCredentials | None:
        """Build adapter verify-credentials input for provider-account updates.

        Returns ``None`` when the update does not touch credentials.
        Provider-specific mappers must override this when update-time
        verification is supported.
        """
        _ = existing_account
        if "provider_data" not in payload.model_fields_set:
            return None
        msg = "Credential verification for provider account updates is not implemented for this provider."
        raise NotImplementedError(msg)

    def resolve_provider_account_response(
        self,
        provider_account: DeploymentProviderAccount,
    ) -> DeploymentProviderAccountGetResponse:
        return DeploymentProviderAccountGetResponse(
            id=provider_account.id,
            name=provider_account.name,
            provider_key=provider_account.provider_key,
            provider_data=self.resolve_provider_account_provider_data(provider_account),
            created_at=provider_account.created_at,
            updated_at=provider_account.updated_at,
        )

    def resolve_provider_account_provider_data(
        self,
        provider_account: DeploymentProviderAccount,
    ) -> dict[str, Any] | None:
        """Return non-sensitive provider metadata for provider-account responses."""
        return {"url": provider_account.provider_url}

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
        _ = payload
        return []

    def util_existing_deployment_resource_key_for_create(
        self,
        payload: DeploymentCreateRequest,
    ) -> str | None:
        """Return provider deployment id to reuse on create, if requested."""
        _ = payload
        raise NotImplementedError

    def util_should_mutate_provider_for_existing_deployment_create(
        self,
        payload: DeploymentCreateRequest,
    ) -> bool:
        """Return whether existing-resource create should call provider update."""
        _ = payload
        raise NotImplementedError

    def util_create_result_from_existing_update(
        self,
        *,
        existing_resource_key: str,
        result: DeploymentUpdateResult,
    ) -> DeploymentCreateResult:
        """Build create-result contract from existing-resource update result.

        Routes use this when create-time onboarding reuses an existing provider
        resource and mutates it through ``adapter.update``.
        """
        _ = (existing_resource_key, result)
        raise NotImplementedError

    def util_create_result_from_existing_resource(
        self,
        *,
        existing_resource_key: str,
    ) -> DeploymentCreateResult:
        """Build create-result contract for DB-only existing-resource onboarding."""
        return DeploymentCreateResult(id=existing_resource_key)

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
        _ = payload
        return FlowVersionPatch()

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

    def shape_deployment_list_result(
        self,
        result: DeploymentListResult,
    ) -> DeploymentListResponse:
        entries = []
        for item in result.deployments:
            item_id = str(item.id).strip()
            if not item_id:
                continue
            item_provider_data = (
                self.shape_deployment_item_data(item.provider_data if isinstance(item.provider_data, dict) else None)
                or {}
            )
            entries.append(
                {
                    "id": item_id,
                    "name": item.name,
                    "type": item.type,
                    "description": getattr(item, "description", None),
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    **item_provider_data,
                }
            )
        return DeploymentListResponse(
            deployments=[],
            page=1,
            size=len(entries),
            total=len(entries),
            provider_data={"entries": entries},
        )

    def shape_llm_list_result(self, result: DeploymentListLlmsResult) -> DeploymentLlmListResponse:
        """Shape adapter LLM listing into the API response model."""
        provider_data = result.provider_result if isinstance(result.provider_result, dict) else None
        return DeploymentLlmListResponse(provider_data=provider_data)

    def shape_config_list_result(
        self,
        result: ConfigListResult,
        *,
        page: int,
        size: int,
    ) -> DeploymentConfigListResponse:
        _ = self._validate_slot(
            self.api_payloads.config_list_result,
            result.provider_result if isinstance(result.provider_result, dict) else None,
        )
        items_all = [item.model_dump(mode="json", exclude_none=True) for item in result.configs]
        total = len(items_all)
        offset = page_offset(page, size)
        provider_result = result.provider_result if isinstance(result.provider_result, dict) else {}
        provider_data: dict[str, Any] = {
            **provider_result,
            "configs": items_all[offset : offset + size],
        }
        return DeploymentConfigListResponse(
            provider_data=provider_data or None,
            page=page,
            size=size,
            total=total,
        )

    def shape_snapshot_list_result(
        self,
        result: SnapshotListResult,
        *,
        page: int,
        size: int,
    ) -> DeploymentSnapshotListResponse:
        _ = self._validate_slot(
            self.api_payloads.snapshot_list_result,
            result.provider_result if isinstance(result.provider_result, dict) else None,
        )
        items_all = [item.model_dump(mode="json", exclude_none=True) for item in result.snapshots]
        total = len(items_all)
        offset = page_offset(page, size)
        provider_result = result.provider_result if isinstance(result.provider_result, dict) else {}
        provider_data: dict[str, Any] = {
            **provider_result,
            "snapshots": items_all[offset : offset + size],
        }
        return DeploymentSnapshotListResponse(
            provider_data=provider_data or None,
            page=page,
            size=size,
            total=total,
        )

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
    ) -> RunCreateResponse:
        provider_result = self.shape_execution_create_provider_data(
            result.provider_result if isinstance(result.provider_result, dict) else None
        )
        return RunCreateResponse(
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def shape_execution_status_result(
        self,
        result: ExecutionStatusResult,
        *,
        deployment_id: UUID,
    ) -> RunStatusResponse:
        provider_result = self.shape_execution_status_provider_data(
            result.provider_result if isinstance(result.provider_result, dict) else None
        )
        return RunStatusResponse(
            deployment_id=deployment_id,
            provider_data=provider_result,
        )

    def util_resource_key_from_execution(
        self,
        result: ExecutionStatusResult | ExecutionCreateResult,
    ) -> str | None:
        """Resolve provider deployment resource key from an execution result.

        The default trusts the top-level ``result.deployment_id``.  Adapters
        that carry the identifier only inside ``provider_result`` can override.
        """
        return str(result.deployment_id or "").strip() or None

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
