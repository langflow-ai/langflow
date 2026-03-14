"""Deployment payload slot taxonomy shared across adapter and API layers."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TypeVar

from lfx.services.adapters.payload import AdapterPayload, PayloadSlot, ProviderPayloadSchemas

T_DeploymentSpec = TypeVar("T_DeploymentSpec", default=AdapterPayload)
T_DeploymentConfig = TypeVar("T_DeploymentConfig", default=AdapterPayload)
T_DeploymentUpdate = TypeVar("T_DeploymentUpdate", default=AdapterPayload)
T_ExecutionInput = TypeVar("T_ExecutionInput", default=AdapterPayload)
T_DeploymentListParams = TypeVar("T_DeploymentListParams", default=AdapterPayload)
T_ConfigListParams = TypeVar("T_ConfigListParams", default=AdapterPayload)
T_SnapshotListParams = TypeVar("T_SnapshotListParams", default=AdapterPayload)
T_DeploymentCreateResult = TypeVar("T_DeploymentCreateResult", default=AdapterPayload)
T_DeploymentOperationResult = TypeVar("T_DeploymentOperationResult", default=AdapterPayload)
T_DeploymentListResult = TypeVar("T_DeploymentListResult", default=AdapterPayload)
T_ConfigListResult = TypeVar("T_ConfigListResult", default=AdapterPayload)
T_SnapshotListResult = TypeVar("T_SnapshotListResult", default=AdapterPayload)
T_ExecutionResult = TypeVar("T_ExecutionResult", default=AdapterPayload)
T_DeploymentItemData = TypeVar("T_DeploymentItemData", default=AdapterPayload)
T_DeploymentStatusData = TypeVar("T_DeploymentStatusData", default=AdapterPayload)
T_ProviderData = TypeVar("T_ProviderData", default=AdapterPayload)
T_ProviderResult = TypeVar("T_ProviderResult", default=AdapterPayload)
T_ListParamsPayload = TypeVar("T_ListParamsPayload", default=AdapterPayload)


@dataclass(frozen=True)
class DeploymentPayloadFields(ProviderPayloadSchemas):
    """Canonical deployment payload slot names for all providers.

    Outbound slots are intentionally operation-specific (create, operation,
    deployment list, config list, snapshot list, execution) so providers can
    expose distinct payload contracts per operation without sharing one
    umbrella ``deployment_result`` shape.

    Ownership boundary:
    this module defines *slot names* (shared structure) for both layers.
    Slot population is layer-specific:
    - adapters populate ``DeploymentPayloadSchemas`` (adapter-side contracts)
    - Langflow mappers populate ``DeploymentApiPayloads`` (API-side contracts)
    """

    # Inbound (request -> adapter)
    deployment_spec: PayloadSlot[T_DeploymentSpec] | None = None
    deployment_config: PayloadSlot[T_DeploymentConfig] | None = None
    deployment_update: PayloadSlot[T_DeploymentUpdate] | None = None
    execution_input: PayloadSlot[T_ExecutionInput] | None = None
    deployment_list_params: PayloadSlot[T_DeploymentListParams] | None = None
    config_list_params: PayloadSlot[T_ConfigListParams] | None = None
    snapshot_list_params: PayloadSlot[T_SnapshotListParams] | None = None

    # Outbound (adapter -> response)
    deployment_create_result: PayloadSlot[T_DeploymentCreateResult] | None = None
    deployment_operation_result: PayloadSlot[T_DeploymentOperationResult] | None = None
    deployment_list_result: PayloadSlot[T_DeploymentListResult] | None = None
    config_list_result: PayloadSlot[T_ConfigListResult] | None = None
    snapshot_list_result: PayloadSlot[T_SnapshotListResult] | None = None
    execution_result: PayloadSlot[T_ExecutionResult] | None = None
    deployment_item_data: PayloadSlot[T_DeploymentItemData] | None = None
    deployment_status_data: PayloadSlot[T_DeploymentStatusData] | None = None


@dataclass(frozen=True)
class DeploymentPayloadSchemas(DeploymentPayloadFields):
    """Adapter-side payload schema registry for deployment providers."""
