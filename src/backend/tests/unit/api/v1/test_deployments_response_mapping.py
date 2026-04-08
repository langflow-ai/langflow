from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentType


def test_shape_deployment_create_result_maps_db_identity_and_provider_result() -> None:
    mapper = BaseDeploymentMapper()
    provider_account_id = uuid4()
    now = datetime.now(timezone.utc)
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        name="db-deployment-name",
        description="db-description",
        deployment_type=DeploymentType.AGENT,
        resource_key="provider-deployment-id",
        created_at=now,
        updated_at=now,
    )
    adapter_result = DeploymentCreateResult(
        id="provider-deployment-id",
        provider_result={"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]},
    )

    response = mapper.shape_deployment_create_result(adapter_result, deployment_row, provider_key="test-provider")

    assert response.id == deployment_row.id
    assert response.provider_id == provider_account_id
    assert response.provider_key == "test-provider"
    assert response.name == deployment_row.name
    assert response.description == "db-description"
    assert response.created_at == now
    assert response.updated_at == now
    assert response.type == DeploymentType.AGENT
    assert response.provider_data == {"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]}
