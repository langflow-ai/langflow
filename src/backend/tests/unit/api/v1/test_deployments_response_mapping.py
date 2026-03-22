from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from langflow.api.v1.deployments import _to_deployment_create_response
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentType


def test_to_deployment_create_response_maps_db_identity_and_provider_result() -> None:
    now = datetime.now(UTC)
    deployment_row = SimpleNamespace(
        id=uuid4(),
        name="db-deployment-name",
        description="db-description",
        deployment_type=DeploymentType.AGENT,
        created_at=now,
        updated_at=now,
    )
    adapter_result = DeploymentCreateResult(
        id="provider-deployment-id",
        provider_result={"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]},
    )

    response = _to_deployment_create_response(adapter_result, deployment_row)

    assert response.id == deployment_row.id
    assert response.name == deployment_row.name
    assert response.description == "db-description"
    assert response.created_at == now
    assert response.updated_at == now
    assert response.provider_data == {"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]}
