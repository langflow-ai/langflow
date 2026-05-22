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
from lfx.log.logger import logger
from lfx.services.adapters.deployment.payloads import DeploymentPayloadFields
from lfx.services.adapters.deployment.schema import (
    BaseFlowArtifact,
    ConfigListParams,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentGetResult,
    DeploymentListLlmsResult,
    DeploymentListParams,
    DeploymentListResult,
    DeploymentType,
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
from lfx.services.adapters.payload import (
    AdapterPayload,
    AdapterPayloadMissingError,
    AdapterPayloadValidationError,
    PayloadSlot,
)
from pydantic import BaseModel

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
    CreateSnapshotBindings,
    FlowVersionPatch,
    ProviderSnapshotBinding,
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


class OuterRequestValidationError(ValueError):
    """Raised when provider_data is invalid in the context of its containing request."""

    def __init__(self, *, model_name: str, detail: str) -> None:
        self.model_name = model_name
        self.detail = detail
        super().__init__(f"Invalid content for request payload '{model_name}'.")


class OuterRequestValidationNotConfiguredError(RuntimeError):
    """Raised when outer-request validation is requested for a model without the hook."""

    def __init__(self, *, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(f"Payload model '{model_name}' does not support outer request validation.")


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
    PROVIDER_LABEL: ClassVar[str | None] = None

    def get_provider_label(self) -> str:
        if self.PROVIDER_LABEL is None:
            msg = f"{self.__class__.__name__} must override PROVIDER_LABEL to be a string."
            raise NotImplementedError(msg)
        return self.PROVIDER_LABEL

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
        _ = (user_id, project_id, db, payload)
        msg = "This deployment provider is not configured for creating deployments."
        raise NotImplementedError(msg)

    async def resolve_deployment_update(
        self,
        *,
        user_id: UUID,
        deployment_db_id: UUID,
        db: AsyncSession,
        payload: DeploymentUpdateRequest,
    ) -> AdapterDeploymentUpdate:
        _ = (user_id, deployment_db_id, db, payload)
        msg = "This deployment provider is not configured for updating deployments."
        raise NotImplementedError(msg)

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

    def resolve_load_from_provider_deployment_list_params(self) -> dict[str, Any] | None:
        """Return provider_params for provider-backed deployment listing.

        Default behavior applies no provider-specific filters.
        """
        return None

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

    async def resolve_deployment_list_adapter_params(
        self,
        *,
        deployment_type: DeploymentType | None,
        provider_params: dict[str, Any] | None,
    ) -> DeploymentListParams | None:
        if deployment_type is None and provider_params is None:
            return None
        return DeploymentListParams(
            deployment_types=[deployment_type] if deployment_type is not None else None,
            provider_params=provider_params,
        )

    async def resolve_config_list_adapter_params(
        self,
        *,
        deployment_resource_key: str | None,
        provider_params: dict[str, Any] | None,
    ) -> ConfigListParams:
        return ConfigListParams(
            deployment_ids=[deployment_resource_key] if deployment_resource_key is not None else None,
            provider_params=provider_params,
        )

    async def resolve_snapshot_list_adapter_params(
        self,
        *,
        deployment_resource_key: str | None,
        provider_params: dict[str, Any] | None,
    ) -> SnapshotListParams:
        return SnapshotListParams(
            deployment_ids=[deployment_resource_key] if deployment_resource_key is not None else None,
            provider_params=provider_params,
        )

    def shape_deployment_list_items(
        self,
        *,
        rows_with_counts: list[tuple[Deployment, int, list[tuple[UUID, str | None]]]],
        has_flow_filter: bool = False,
        provider_key: str,
        provider_data_by_resource_key: dict[str, dict[str, Any]] | None = None,
    ) -> list[DeploymentListItem]:
        _ = provider_data_by_resource_key
        return [
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

    def resolve_deployment_model_for_create(
        self,
        *,
        result: DeploymentCreateResult,
        user_id: UUID,
        project_id: UUID,
        deployment_provider_account_id: UUID,
    ) -> Deployment:
        """Assemble the DB model for a deployment create.

        Provider mappers own request-specific deployment metadata extraction.
        The base mapper has no provider-agnostic source for required DB fields
        such as the display label.
        """
        _ = (result, user_id, project_id, deployment_provider_account_id)
        msg = "This deployment provider is not configured for creating local deployment records."
        raise NotImplementedError(msg)

    def resolve_deployment_model_from_existing_resource_for_create(
        self,
        *,
        payload: DeploymentCreateRequest,
        existing_provider_resource: DeploymentGetResult,
        user_id: UUID,
        project_id: UUID,
        deployment_provider_account_id: UUID,
    ) -> Deployment:
        """Assemble the DB model for onboarding an existing provider resource."""
        _ = (payload, existing_provider_resource, user_id, project_id, deployment_provider_account_id)
        msg = "This deployment provider is not configured for onboarding existing deployment resources."
        raise NotImplementedError(msg)

    def resolve_kwargs_for_metadata_update(self, result: DeploymentUpdateResult) -> dict[str, Any]:
        """Assemble Deployment metadata update kwargs from a provider update result.

        Provider mappers own provider-result metadata extraction. The base
        mapper has no provider-agnostic source for mutable DB cache fields.
        """
        _ = result
        msg = "This deployment provider is not configured for updating local deployment metadata."
        raise NotImplementedError(msg)

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
        msg = "This deployment provider is not configured for verifying provider account updates."
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

    def util_create_result_from_existing_resource(
        self,
        *,
        existing_resource: DeploymentGetResult,
    ) -> DeploymentCreateResult:
        """Build create-result contract for DB-only existing-resource onboarding."""
        _ = existing_resource
        msg = "This deployment provider is not configured for onboarding existing deployment resources."
        raise NotImplementedError(msg)

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

    def extract_snapshot_bindings(
        self,
        provider_view: DeploymentListResult,
    ) -> list[ProviderSnapshotBinding]:
        """Extract per-deployment snapshot bindings from an already-fetched provider list response.

        Returns a flat list of (resource_key, snapshot_id) pairs representing
        the authoritative binding state on the provider. Deployments absent
        from the response (e.g. deleted) produce no entries.

        Subclasses MUST override this method.

        Why this raises instead of returning ``[]``:
        the downstream consumer ``delete_unbound_attachments`` treats an
        empty ``bindings`` list together with a non-empty ``deployment_ids``
        set as the explicit instruction "delete every local attachment for
        these deployments." A silent ``return []`` from this method would
        therefore trigger a **destructive mass-delete of user attachment
        data** for any provider that inherits the base implementation.
        Raising ``NotImplementedError`` prevents that destructive
        interpretation entirely: call sites either guard with
        ``except NotImplementedError`` (skipping the destructive sync) or
        surface a loud failure pointing at the unimplemented method.
        """
        _ = provider_view
        msg = "This deployment provider is not configured for syncing snapshots for multiple deployments."
        raise NotImplementedError(msg)

    def extract_list_item_provider_data(
        self,
        provider_view: DeploymentListResult,
    ) -> dict[str, dict[str, Any]]:
        """Extract per-deployment list-item provider_data from an already-fetched provider list response.

        Returns a {resource_key -> provider_data} dict. Base returns an empty
        dict so providers without per-item list metadata omit provider_data.
        """
        _ = provider_view
        return {}

    def extract_metadata_for_list(
        self,
        provider_view: DeploymentListResult,
    ) -> dict[str, dict[str, Any]]:
        """Resolve resource_key -> CRUD kwargs for local metadata sync."""
        _ = provider_view
        msg = "This deployment provider is not configured for syncing metadata for multiple deployments."
        raise NotImplementedError(msg)

    def extract_metadata_for_get(
        self,
        get_result: DeploymentGetResult,
    ) -> dict[str, Any]:
        """Resolve CRUD kwargs for local metadata sync from a provider GET result."""
        _ = get_result
        msg = "This deployment provider is not configured for syncing metadata for a deployment."
        raise NotImplementedError(msg)

    def extract_snapshot_bindings_for_get(
        self,
        get_result: DeploymentGetResult,
        *,
        resource_key: str,
    ) -> list[ProviderSnapshotBinding]:
        """Extract bindings from a single-deployment provider GET payload.

        Subclasses MUST override this method.

        Why this raises instead of returning ``[]``:
        the downstream consumer ``delete_unbound_attachments`` treats an
        empty ``bindings`` list together with a non-empty ``deployment_ids``
        set as the explicit instruction "delete every local attachment for
        this deployment." A silent ``return []`` from this method would
        therefore trigger a **destructive mass-delete of user attachment
        data** for the GETted deployment for any provider that inherits
        the base implementation. Raising ``NotImplementedError`` prevents
        that destructive interpretation entirely: the GET call site
        guards with ``except NotImplementedError`` and skips the
        destructive sync (returning unverified attachment counts) rather
        than wiping local state.
        """
        _ = get_result, resource_key
        msg = "This deployment provider is not configured for syncing snapshots for a deployment."
        raise NotImplementedError(msg)

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

    def shape_deployment_get_data(
        self,
        provider_data: AdapterPayload | None,
        *,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        """Shape provider_data for single-deployment GET responses."""
        _ = provider_data, name
        msg = (
            "BaseDeploymentMapper does not implement shape_deployment_get_data; "
            "must be implemented by subclasses (e.g. watsonx_orchestrate). "
            "GET provider_data shaping is unavailable for this provider."
        )
        raise NotImplementedError(msg)

    @staticmethod
    def _validate_slot(
        slot: PayloadSlot[Any] | None,
        raw: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Validate a payload dict against a configured API slot."""
        if raw is None or slot is None:
            return raw
        return slot.apply(raw)

    def parse_adapter_slot(
        self,
        *,
        slot: PayloadSlot[Any] | None,
        slot_name: str,
        raw: Any,
        operation: str = "this operation",
    ) -> Any:
        """Parse a non-user-supplied adapter-boundary payload, raising 500 on failure.

        Use for adapter/provider results and mapper-built payloads headed to the adapter.
        Failures are internal errors — the user cannot fix them.
        ``slot_name`` is logged for debugging but not exposed to the user.
        See ``parse_api_request_slot`` for user-supplied input.
        """
        provider_label = self.get_provider_label()
        if slot is None:
            logger.error("Payload slot '%s' is not configured for %s", slot_name, provider_label)
            msg = f"The {provider_label} integration is not configured for {operation}."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            return slot.parse(raw)
        except AdapterPayloadMissingError as exc:
            logger.error("Empty adapter payload for slot '%s' (%s)", slot_name, provider_label)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Empty result while {operation} ({provider_label}).",
            ) from exc
        except AdapterPayloadValidationError as exc:
            detail = exc.format_first_error()
            logger.error("Invalid adapter payload for slot '%s' (%s): %s", slot_name, provider_label, detail)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected result while {operation} ({provider_label}): {detail}",
            ) from exc

    def parse_api_request_slot(
        self,
        *,
        slot: PayloadSlot[Any] | None,
        slot_name: str,
        raw: Any,
        outer_payload: Any | None = None,
    ) -> Any:
        """Parse a user-supplied API payload, raising 422 on failure.

        Use for data sent **by** the user in the API request (inbound).
        Failures are input errors — the user can fix them.
        ``slot_name`` is logged for debugging but not exposed to the user.
        See ``parse_adapter_slot`` for adapter-boundary payloads.
        """
        provider_label = self.get_provider_label()
        if slot is None:
            logger.error("Payload slot '%s' is not configured for %s", slot_name, provider_label)
            msg = f"The {provider_label} integration is not configured for this operation."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        try:
            parsed = slot.parse(raw)
        except AdapterPayloadMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing provider_data for {provider_label}.",
            ) from exc
        except AdapterPayloadValidationError as exc:
            detail = exc.format_first_error()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_data for {provider_label}: {detail}",
            ) from exc
        if outer_payload is None:
            return parsed
        try:
            self.validate_with_outer_request(parsed, outer_payload)
        except OuterRequestValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid provider_data for {provider_label}: {exc.detail}",
            ) from exc
        except OuterRequestValidationNotConfiguredError as exc:
            logger.error(
                "Payload slot '%s' does not support outer request validation for %s: %s",
                slot_name,
                provider_label,
                exc,
            )
            msg = f"The {provider_label} integration is not configured for this operation."
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc
        return parsed

    @staticmethod
    def validate_with_outer_request(parsed: BaseModel, outer_payload: BaseModel) -> None:
        validate_with_outer_fields = getattr(parsed, "validate_with_outer_fields", None)
        model_name = parsed.__class__.__name__
        if not callable(validate_with_outer_fields):
            raise OuterRequestValidationNotConfiguredError(model_name=model_name)
        try:
            validate_with_outer_fields(outer_payload)
        except ValueError as exc:
            detail = str(exc) or "Invalid content for request payload."
            raise OuterRequestValidationError(model_name=model_name, detail=detail) from exc
