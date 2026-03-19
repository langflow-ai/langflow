"""Helpers used to keep wxO deployment create flow lean."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.adapters.deployment.exceptions import DeploymentError, InvalidContentError
from lfx.services.adapters.payload import AdapterPayloadValidationError

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxCreateSnapshotBinding,
    WatsonxDeploymentCreateResultData,
    WatsonxFlowArtifactProviderData,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
    from lfx.services.adapters.deployment.schema import BaseFlowArtifact


def validate_create_flow_provider_data(
    *,
    payload_schemas: DeploymentPayloadSchemas,
    flow_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]],
) -> list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]]:
    """Validate and normalize flow artifact provider_data via adapter payload slot."""
    slot = payload_schemas.flow_artifact
    if slot is None:
        msg = f"{ErrorPrefix.CREATE.value} Required slot 'flow_artifact' is not configured."
        raise DeploymentError(message=msg, error_code="deployment_error")

    validated_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]] = []
    for flow_payload in flow_payloads:
        provider_data_raw = flow_payload.provider_data if isinstance(flow_payload.provider_data, dict) else {}
        try:
            provider_data = slot.apply(provider_data_raw)
        except AdapterPayloadValidationError as exc:
            msg = (
                "Flow payload must include provider_data with non-empty "
                "'project_id' and 'source_ref' for Watsonx deployment."
            )
            raise InvalidContentError(message=msg) from exc
        validated_payloads.append(flow_payload.model_copy(update={"provider_data": provider_data}))
    return validated_payloads


def build_create_provider_result(
    *,
    payload_schemas: DeploymentPayloadSchemas,
    snapshot_bindings: list[WatsonxCreateSnapshotBinding],
) -> dict:
    """Build create provider_result through deployment_create_result slot."""
    slot = payload_schemas.deployment_create_result
    if slot is None:
        msg = f"{ErrorPrefix.CREATE.value} Required slot 'deployment_create_result' is not configured."
        raise DeploymentError(message=msg, error_code="deployment_error")
    try:
        return slot.apply(
            WatsonxDeploymentCreateResultData(snapshot_bindings=snapshot_bindings).model_dump(exclude_none=True)
        )
    except AdapterPayloadValidationError as exc:
        msg = f"{ErrorPrefix.CREATE.value} Invalid create result payload for deployment_create_result slot."
        raise DeploymentError(message=msg, error_code="deployment_error") from exc
