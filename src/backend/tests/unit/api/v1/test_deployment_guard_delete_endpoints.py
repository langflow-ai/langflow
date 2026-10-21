"""Project-delete deployment guards, exercised through the real app.

Each test seeds real deployment rows and calls the HTTP route, so the app-level
guard, the guard-retry wrapper, the flow-to-project remap and the global
``DeploymentGuardError`` -> 409 handler all run together.

Flow delete, bulk flow delete and flow move guards are covered in
``test_flows.py``; project create/update move guards in ``test_projects.py``.
"""

from uuid import UUID

from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.deployment.exceptions import get_friendly_guard_detail

PROJECT_GUARD_DETAIL = get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS")


async def _seed_deployment(*, user_id: UUID, project_id: UUID, flow_id: UUID | None = None) -> None:
    """Insert a deployment into ``project_id``; attach a version of ``flow_id`` to it when given."""
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import (
        DeploymentProviderAccount,
        DeploymentProviderKey,
    )
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )
    from langflow.services.deps import session_scope
    from lfx.services.adapters.deployment.schema import DeploymentType

    suffix = project_id.hex[:8]
    async with session_scope() as session:
        provider = DeploymentProviderAccount(
            user_id=user_id,
            name=f"provider-{suffix}",
            provider_tenant_id="tenant-1",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url=f"https://provider-{suffix}.example.com",
            api_key="encrypted-value",  # pragma: allowlist secret
        )
        session.add(provider)
        await session.flush()

        deployment = Deployment(
            user_id=user_id,
            project_id=project_id,
            deployment_provider_account_id=provider.id,
            resource_key=f"rk-{suffix}",
            display_name=f"deployment-{suffix}",
            deployment_type=DeploymentType.AGENT,
        )
        session.add(deployment)
        await session.flush()

        if flow_id is not None:
            flow_version = FlowVersion(
                flow_id=flow_id,
                user_id=user_id,
                version_number=1,
                data={"nodes": [], "edges": []},
            )
            session.add(flow_version)
            await session.flush()

            session.add(
                FlowVersionDeploymentAttachment(
                    user_id=user_id,
                    flow_version_id=flow_version.id,
                    deployment_id=deployment.id,
                    provider_snapshot_id=f"snapshot-{suffix}",
                )
            )
        await session.commit()


async def _create_project(client: AsyncClient, headers: dict, name: str) -> str:
    response = await client.post(
        "api/v1/projects/",
        json={"name": name, "description": "", "flows_list": [], "components_list": []},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def _create_flow(client: AsyncClient, headers: dict, *, project_id: str, name: str) -> str:
    response = await client.post(
        "api/v1/flows/",
        json={"name": name, "folder_id": project_id, "data": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def test_delete_project_with_deployment_and_no_flows_returns_409(
    client: AsyncClient,
    logged_in_headers: dict,
    active_user,
):
    """A deployment with no attached flow is caught by the app-level project check, not a flow guard."""
    project_id = await _create_project(client, logged_in_headers, "guard-empty-project")
    await _seed_deployment(user_id=active_user.id, project_id=UUID(project_id))

    delete_resp = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)

    assert delete_resp.status_code == status.HTTP_409_CONFLICT, delete_resp.text
    assert delete_resp.json()["detail"] == PROJECT_GUARD_DETAIL
    project_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert project_resp.status_code == status.HTTP_200_OK


async def test_delete_project_with_deployed_flow_reports_project_guard_and_deletes_nothing(
    client: AsyncClient,
    logged_in_headers: dict,
    active_user,
):
    """The flow guard is remapped to the project guard, and a blocked delete removes no flows."""
    project_id = await _create_project(client, logged_in_headers, "guard-flow-project")
    undeployed_flow_id = await _create_flow(
        client, logged_in_headers, project_id=project_id, name="guard-undeployed-flow"
    )
    deployed_flow_id = await _create_flow(client, logged_in_headers, project_id=project_id, name="guard-deployed-flow")
    await _seed_deployment(user_id=active_user.id, project_id=UUID(project_id), flow_id=UUID(deployed_flow_id))

    delete_resp = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)

    assert delete_resp.status_code == status.HTTP_409_CONFLICT, delete_resp.text
    assert delete_resp.json()["detail"] == PROJECT_GUARD_DETAIL
    project_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert project_resp.status_code == status.HTTP_200_OK
    for flow_id in (undeployed_flow_id, deployed_flow_id):
        flow_resp = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
        assert flow_resp.status_code == status.HTTP_200_OK, f"flow {flow_id} was deleted by a blocked project delete"
