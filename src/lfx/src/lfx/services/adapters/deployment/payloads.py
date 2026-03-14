"""Deployment payload slot taxonomy shared across adapter and API layers."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from typing_extensions import TypeVar

from lfx.services.adapters.payload import AdapterPayload, PayloadSlot, ProviderPayloadSchemas

# This pairing is an explicit boundary design:
# - payload value typevars default to dict for open provider extension points
# - slot model typevars are BaseModel-bound for strict parse/dump contracts
# Together this preserves a stable pluggable surface while keeping validation
# strict at slot boundaries.
# Inbound payload pairs
T_DeploymentSpec = TypeVar("T_DeploymentSpec", default=AdapterPayload)
T_DeploymentSpecModel = TypeVar("T_DeploymentSpecModel", bound=BaseModel, default=BaseModel)

T_DeploymentConfig = TypeVar("T_DeploymentConfig", default=AdapterPayload)
T_DeploymentConfigModel = TypeVar("T_DeploymentConfigModel", bound=BaseModel, default=BaseModel)

T_DeploymentUpdate = TypeVar("T_DeploymentUpdate", default=AdapterPayload)
T_DeploymentUpdateModel = TypeVar("T_DeploymentUpdateModel", bound=BaseModel, default=BaseModel)

T_ExecutionInput = TypeVar("T_ExecutionInput", default=AdapterPayload)
T_ExecutionInputModel = TypeVar("T_ExecutionInputModel", bound=BaseModel, default=BaseModel)

T_DeploymentListParams = TypeVar("T_DeploymentListParams", default=AdapterPayload)
T_DeploymentListParamsModel = TypeVar("T_DeploymentListParamsModel", bound=BaseModel, default=BaseModel)

T_ConfigListParams = TypeVar("T_ConfigListParams", default=AdapterPayload)
T_ConfigListParamsModel = TypeVar("T_ConfigListParamsModel", bound=BaseModel, default=BaseModel)

T_SnapshotListParams = TypeVar("T_SnapshotListParams", default=AdapterPayload)
T_SnapshotListParamsModel = TypeVar("T_SnapshotListParamsModel", bound=BaseModel, default=BaseModel)

# Outbound payload pairs
T_DeploymentCreateResult = TypeVar("T_DeploymentCreateResult", default=AdapterPayload)
T_DeploymentCreateResultModel = TypeVar("T_DeploymentCreateResultModel", bound=BaseModel, default=BaseModel)

T_DeploymentOperationResult = TypeVar("T_DeploymentOperationResult", default=AdapterPayload)
T_DeploymentOperationResultModel = TypeVar("T_DeploymentOperationResultModel", bound=BaseModel, default=BaseModel)

T_DeploymentListResult = TypeVar("T_DeploymentListResult", default=AdapterPayload)
T_DeploymentListResultModel = TypeVar("T_DeploymentListResultModel", bound=BaseModel, default=BaseModel)

T_ConfigListResult = TypeVar("T_ConfigListResult", default=AdapterPayload)
T_ConfigListResultModel = TypeVar("T_ConfigListResultModel", bound=BaseModel, default=BaseModel)

T_SnapshotListResult = TypeVar("T_SnapshotListResult", default=AdapterPayload)
T_SnapshotListResultModel = TypeVar("T_SnapshotListResultModel", bound=BaseModel, default=BaseModel)

T_ExecutionResult = TypeVar("T_ExecutionResult", default=AdapterPayload)
T_ExecutionResultModel = TypeVar("T_ExecutionResultModel", bound=BaseModel, default=BaseModel)

T_DeploymentItemData = TypeVar("T_DeploymentItemData", default=AdapterPayload)
T_DeploymentItemDataModel = TypeVar("T_DeploymentItemDataModel", bound=BaseModel, default=BaseModel)

T_DeploymentStatusData = TypeVar("T_DeploymentStatusData", default=AdapterPayload)
T_DeploymentStatusDataModel = TypeVar("T_DeploymentStatusDataModel", bound=BaseModel, default=BaseModel)

# Shared payload-only typevars
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
    deployment_spec: PayloadSlot[T_DeploymentSpecModel] | None = None
    deployment_config: PayloadSlot[T_DeploymentConfigModel] | None = None
    deployment_update: PayloadSlot[T_DeploymentUpdateModel] | None = None
    execution_input: PayloadSlot[T_ExecutionInputModel] | None = None
    deployment_list_params: PayloadSlot[T_DeploymentListParamsModel] | None = None
    config_list_params: PayloadSlot[T_ConfigListParamsModel] | None = None
    snapshot_list_params: PayloadSlot[T_SnapshotListParamsModel] | None = None

    # Outbound (adapter -> response)
    deployment_create_result: PayloadSlot[T_DeploymentCreateResultModel] | None = None
    deployment_operation_result: PayloadSlot[T_DeploymentOperationResultModel] | None = None
    deployment_list_result: PayloadSlot[T_DeploymentListResultModel] | None = None
    config_list_result: PayloadSlot[T_ConfigListResultModel] | None = None
    snapshot_list_result: PayloadSlot[T_SnapshotListResultModel] | None = None
    execution_result: PayloadSlot[T_ExecutionResultModel] | None = None
    deployment_item_data: PayloadSlot[T_DeploymentItemDataModel] | None = None
    deployment_status_data: PayloadSlot[T_DeploymentStatusDataModel] | None = None


@dataclass(frozen=True)
class DeploymentPayloadSchemas(DeploymentPayloadFields):
    """Adapter-side payload schema registry for deployment providers."""
