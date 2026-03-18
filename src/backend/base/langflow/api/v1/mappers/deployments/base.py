# ruff: noqa: ARG002
"""Base deployment payload mapper contracts for API <-> adapter transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from lfx.services.adapters.deployment.payloads import DeploymentPayloadFields
from lfx.services.adapters.deployment.schema import (
    ConfigDeploymentBindingUpdate,
    DeploymentType,
    DeploymentUpdateResult,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentUpdate as AdapterDeploymentUpdate,
)
from lfx.services.adapters.payload import PayloadSlot

from langflow.api.v1.schemas.deployments import DeploymentUpdateRequest, DeploymentUpdateResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.database.models.deployment.model import Deployment


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
    inbound ``resolve_*`` methods return the original dict unless an
    API payload slot is configured for that field, in which case the
    slot ``apply`` policy is used.
    Outbound ``shape_*`` methods return provider payloads unchanged, including
    the operation-specific result shapers:
    ``shape_deployment_create_result``, ``shape_deployment_operation_result``,
    ``shape_deployment_list_result``, ``shape_config_list_result``, and
    ``shape_snapshot_list_result``.

    Provider-specific mappers override only the methods that need
    Langflow-aware resolution or payload reshaping.
    """

    api_payloads: ClassVar[DeploymentApiPayloads] = DeploymentApiPayloads()

    async def resolve_deployment_spec(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_spec, raw)

    async def resolve_deployment_config(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_config, raw)

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
        *,
        description: str | None = None,
    ) -> DeploymentUpdateResponse:
        provider_data = result.provider_result if isinstance(result.provider_result, dict) else None
        return DeploymentUpdateResponse(
            id=deployment_row.id,
            name=deployment_row.name,
            description=description,
            # TODO: Make deployment.deployment_type
            # a DeploymentType enum column in the
            # DB model, and remove this fallback.
            type=DeploymentType(deployment_row.deployment_type or DeploymentType.AGENT.value),
            created_at=deployment_row.created_at,
            updated_at=deployment_row.updated_at,
            provider_data=provider_data,
        )

    def resolve_created_snapshot_ids(self, result: DeploymentUpdateResult) -> list[str]:
        """Return snapshot ids created during this update.

        Base behavior treats ``result.snapshot_ids`` as created ids.
        Provider-specific mappers may override this when the adapter uses
        ``snapshot_ids`` for finalized bindings and exposes created ids in
        provider-specific result payloads.
        """
        return [str(snapshot_id).strip() for snapshot_id in result.snapshot_ids if str(snapshot_id).strip()]

    def resolve_flow_version_patch(self, payload: DeploymentUpdateRequest) -> tuple[list[UUID], list[UUID]]:
        """Resolve flow-version attachment adds/removes represented by this update request."""
        if payload.flow_version_ids is None:
            return [], []
        return list(payload.flow_version_ids.add or []), list(payload.flow_version_ids.remove or [])

    def shape_deployment_operation_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_deployment_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_config_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_snapshot_list_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

    def shape_execution_result(self, provider_result: dict[str, Any] | None) -> dict[str, Any] | None:
        return provider_result

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


class DeploymentMapperRegistry:
    """Registry of per-provider deployment mappers."""

    _default: BaseDeploymentMapper
    _mapper_classes: dict[str, type[BaseDeploymentMapper]]
    _mapper_instances: dict[str, BaseDeploymentMapper]

    def __init__(self) -> None:
        self._default = BaseDeploymentMapper()
        self._mapper_classes = {}
        self._mapper_instances = {}

    def register(self, provider_key: str, mapper_class: type[BaseDeploymentMapper]) -> None:
        if not issubclass(mapper_class, BaseDeploymentMapper):
            msg = "mapper_class must inherit from BaseDeploymentMapper"
            raise TypeError(msg)
        self._mapper_classes[provider_key] = mapper_class
        self._mapper_instances.pop(provider_key, None)

    def get(self, provider_key: str) -> BaseDeploymentMapper:
        mapper_class = self._mapper_classes.get(provider_key)
        if mapper_class is None:
            return self._default
        if provider_key not in self._mapper_instances:
            self._mapper_instances[provider_key] = mapper_class()
        return self._mapper_instances[provider_key]
