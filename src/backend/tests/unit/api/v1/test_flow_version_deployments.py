"""Deployment-association behavior for Flow Version list API."""

from uuid import UUID, uuid4

from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict, name: str = "version-test-flow") -> dict:
    payload = {
        "name": name,
        "description": "flow for version deployment tests",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _create_snapshot(client: AsyncClient, headers: dict, flow_id: str, description: str | None = None) -> dict:
    body = {"description": description} if description else {}
    resp = await client.post(f"api/v1/flows/{flow_id}/versions/", json=body, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def test_list_versions_supports_deployment_ids_filter_single_value(
    client: AsyncClient,
    logged_in_headers,
    active_user,
):
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.deps import session_scope

    provider_resp = await client.post(
        "api/v1/deployments/providers",
        json={
            "provider_tenant_id": "tenant-version-filter",
            "provider_key": "watsonx-orchestrate",
            "provider_url": "https://example.ibm.com",
            "api_key": "secret-api-key",  # pragma: allowlist secret
        },
        headers=logged_in_headers,
    )
    assert provider_resp.status_code == status.HTTP_201_CREATED
    provider_id = UUID(provider_resp.json()["id"])

    flow = await _create_flow(client, logged_in_headers, name="version-filter-flow")
    version_1 = await _create_snapshot(client, logged_in_headers, flow["id"], description="attached")
    version_2 = await _create_snapshot(client, logged_in_headers, flow["id"], description="not-attached")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        deployment = Deployment(
            resource_key=f"dep-{uuid4().hex[:8]}",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=provider_id,
            name=f"deployment-{uuid4().hex[:8]}",
        )
        session.add(deployment)
        await session.flush()

        session.add(
            FlowVersionDeploymentAttachment(
                user_id=active_user.id,
                flow_version_id=UUID(version_1["id"]),
                deployment_id=deployment.id,
            )
        )
        await session.flush()
        deployment_row_id = str(deployment.id)

    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"deployment_ids": deployment_row_id},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert [entry["id"] for entry in body["entries"]] == [version_1["id"]]
    assert body["deployment_counts"][version_1["id"]] == 1
    assert version_2["id"] not in [entry["id"] for entry in body["entries"]]


async def test_list_versions_supports_deployment_ids_filter_with_counts(
    client: AsyncClient,
    logged_in_headers,
    active_user,
):
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.deps import session_scope

    provider_resp = await client.post(
        "api/v1/deployments/providers",
        json={
            "provider_tenant_id": "tenant-version-multi-filter",
            "provider_key": "watsonx-orchestrate",
            "provider_url": "https://example.ibm.com",
            "api_key": "secret-api-key",  # pragma: allowlist secret
        },
        headers=logged_in_headers,
    )
    assert provider_resp.status_code == status.HTTP_201_CREATED
    provider_id = UUID(provider_resp.json()["id"])

    flow = await _create_flow(client, logged_in_headers, name="version-multi-filter-flow")
    version_1 = await _create_snapshot(client, logged_in_headers, flow["id"], description="attached-one")
    version_2 = await _create_snapshot(client, logged_in_headers, flow["id"], description="attached-two")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        deployment_1 = Deployment(
            resource_key=f"dep-{uuid4().hex[:8]}",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=provider_id,
            name=f"deployment-{uuid4().hex[:8]}",
        )
        deployment_2 = Deployment(
            resource_key=f"dep-{uuid4().hex[:8]}",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=provider_id,
            name=f"deployment-{uuid4().hex[:8]}",
        )
        session.add(deployment_1)
        session.add(deployment_2)
        await session.flush()

        session.add(
            FlowVersionDeploymentAttachment(
                user_id=active_user.id,
                flow_version_id=UUID(version_1["id"]),
                deployment_id=deployment_1.id,
            )
        )
        session.add(
            FlowVersionDeploymentAttachment(
                user_id=active_user.id,
                flow_version_id=UUID(version_2["id"]),
                deployment_id=deployment_2.id,
            )
        )
        await session.flush()
        deployment_1_id = str(deployment_1.id)
        deployment_2_id = str(deployment_2.id)

    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params=[
            ("deployment_ids", deployment_1_id),
            ("deployment_ids", deployment_2_id),
        ],
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert {entry["id"] for entry in body["entries"]} == {version_1["id"], version_2["id"]}
    assert body["deployment_counts"][version_1["id"]] == 1
    assert body["deployment_counts"][version_2["id"]] == 1
