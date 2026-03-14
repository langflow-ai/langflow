# ruff: noqa: ARG002
"""Base deployment payload mapper contracts for API <-> adapter transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from lfx.services.adapters.deployment.payloads import DeploymentPayloadFields
from lfx.services.adapters.payload import PayloadSlot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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

    async def resolve_deployment_update(self, raw: dict[str, Any] | None, db: AsyncSession) -> dict[str, Any] | None:
        return self._validate_slot(self.api_payloads.deployment_update, raw)

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
    _mappers: dict[str, BaseDeploymentMapper]

    def __init__(self) -> None:
        self._default = BaseDeploymentMapper()
        self._mappers = {}

    def register(self, provider_key: str, mapper: BaseDeploymentMapper) -> None:
        if not isinstance(mapper, BaseDeploymentMapper):
            msg = "mapper must be an instance of BaseDeploymentMapper"
            raise TypeError(msg)
        self._mappers[provider_key] = mapper

    def get(self, provider_key: str) -> BaseDeploymentMapper:
        return self._mappers.get(provider_key, self._default)
