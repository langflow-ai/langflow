from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import status
from langflow.api.v1 import deployment as deployment_api
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history_deployment_attachment.model import (
    FlowHistoryDeploymentAttachment,
)
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from lfx.services.deployment.schema import (
    ArtifactType,
    ConfigItemResult,
    ConfigListResult,
    ConfigResult,
    DeploymentCreateResult,
    DeploymentItem,
    DeploymentList,
    DeploymentType,
    DeploymentUpdateResult,
    SnapshotListResult,
    SnapshotResult,
)
from sqlmodel import select


def _provider_payload(
    *,
    account_id: str | None = "tenant-1",
    provider_key: str | None = "watsonx-orchestrate",
    backend_url: str = "https://example.ibm.com",
    api_key: str = "secret-api-key",
) -> dict:
    payload = {
        "backend_url": backend_url,
        "api_key": api_key,
    }
    if account_id is not None:
        payload["account_id"] = account_id
    if provider_key is not None:
        payload["provider_key"] = provider_key
    return payload


async def _create_provider(client, headers: dict, account_id: str) -> dict:
    response = await client.post(
        "api/v1/deployments/providers/",
        json=_provider_payload(account_id=account_id),
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


async def test_list_provider_accounts_is_paginated(client, logged_in_headers):
    await _create_provider(client, logged_in_headers, "tenant-1")
    await _create_provider(client, logged_in_headers, "tenant-2")
    await _create_provider(client, logged_in_headers, "tenant-3")

    page_one = await client.get(
        "api/v1/deployments/providers/",
        params={"page": 1, "size": 2},
        headers=logged_in_headers,
    )
    assert page_one.status_code == status.HTTP_200_OK
    body_one = page_one.json()
    assert body_one["page"] == 1
    assert body_one["size"] == 2
    assert body_one["total"] >= 3
    assert len(body_one["deployment_providers"]) == 2

    page_two = await client.get(
        "api/v1/deployments/providers/",
        params={"page": 2, "size": 2},
        headers=logged_in_headers,
    )
    assert page_two.status_code == status.HTTP_200_OK
    body_two = page_two.json()
    assert body_two["page"] == 2
    assert body_two["size"] == 2
    assert body_two["total"] == body_one["total"]
    assert len(body_two["deployment_providers"]) >= 1


class _FakeAdapter:
    def __init__(self) -> None:
        self.last_update_payload = None

    async def list_deployments(self, *, deployment_type=None, filter_options=None, **_):
        ids = ((filter_options.provider_filter or {}) if filter_options else {}).get("ids", [])
        kept = []
        if "keep-resource" in ids:
            kept.append(
                DeploymentItem(
                    id="keep-resource",
                    name="Keep Deployment",
                    type=deployment_type or DeploymentType.AGENT,
                )
            )
        return DeploymentList(deployments=kept, deployment_type=deployment_type)

    async def update_deployment(self, *, deployment_id, **_) -> DeploymentUpdateResult:
        self.last_update_payload = _.get("update_data")
        return DeploymentUpdateResult(id=deployment_id)

    async def create_snapshots(self, *, snapshot_items, **_) -> SnapshotResult:
        ids = [f"snapshot-{idx}" for idx, _ in enumerate(snapshot_items.raw_payloads, start=1)]
        return SnapshotResult(ids=ids)


class _CreateCaptureAdapter:
    def __init__(self) -> None:
        self.received_payload = None

    async def create_deployment(self, *, deployment, **_) -> DeploymentCreateResult:
        self.received_payload = deployment
        return DeploymentCreateResult(
            id="provider-deployment-1",
            name=deployment.spec.name,
            description=deployment.spec.description,
            type=deployment.spec.type,
            provider_result={"created_snapshot_ids": ["provider-snapshot-1"]},
        )


class _ConfigsAndSnapshotsAdapter:
    def __init__(self) -> None:
        self.last_artifact_type = None
        self.created_config = None
        self.updated_config = None
        self.deleted_config_id = None

    async def list_snapshots(self, *, artifact_type=None, **_) -> SnapshotListResult:
        self.last_artifact_type = artifact_type
        return SnapshotListResult(
            snapshots=[],
            provider_result={"source": "test"},
            artifact_type=ArtifactType.FLOW,
        )

    async def create_deployment_config(self, *, config, **_) -> ConfigResult:
        self.created_config = config
        return ConfigResult(id="cfg-created", provider_result={"source": "test"})

    async def list_deployment_configs(self, **_) -> ConfigListResult:
        return ConfigListResult(
            configs=[
                ConfigItemResult(
                    id="cfg-listed",
                    name="listed-config",
                    description="listed config from adapter",
                    provider_data={},
                )
            ],
            provider_result={"source": "test"},
        )

    async def get_deployment_config(self, *, config_id: str, **_) -> ConfigItemResult:
        return ConfigItemResult(
            id=config_id,
            name="single-config",
            description="single config from adapter",
            provider_data={},
        )

    async def update_deployment_config(self, *, config_id: str, update_data, **_) -> ConfigResult:
        self.updated_config = (config_id, update_data)
        return ConfigResult(id=config_id, provider_result={"source": "test"})

    async def delete_deployment_config(self, *, config_id: str, **_) -> None:
        self.deleted_config_id = config_id


async def test_deployments_lazy_sync_prunes_stale_rows(client, logged_in_headers, active_user, monkeypatch):
    provider = await _create_provider(client, logged_in_headers, "tenant-lazy-sync")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        keep_deployment = Deployment(
            resource_key="keep-resource",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider["id"]),
            name=f"deployment-keep-{uuid4().hex[:8]}",
        )
        session.add(keep_deployment)
        await session.flush()

        flow = Flow(
            name=f"flow-keep-{uuid4().hex[:8]}",
            user_id=active_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()

        flow_history = FlowHistory(
            flow_id=flow.id,
            user_id=active_user.id,
            data={"nodes": [], "edges": []},
            version_number=1,
            description="checkpoint",
        )
        session.add(flow_history)
        await session.flush()

        session.add(
            FlowHistoryDeploymentAttachment(
                user_id=active_user.id,
                history_id=flow_history.id,
                deployment_id=keep_deployment.id,
            )
        )
        session.add(
            Deployment(
                resource_key="stale-resource",
                user_id=active_user.id,
                project_id=folder.id,
                provider_account_id=UUID(provider["id"]),
                name=f"deployment-stale-{uuid4().hex[:8]}",
            )
        )

    async def _mock_resolve_adapter(*_, **__):
        return _FakeAdapter()

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.get(
        "api/v1/deployments",
        params={"provider_id": provider["id"], "page": 1, "size": 10},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 10
    assert [item["resource_key"] for item in body["deployments"]] == ["keep-resource"]
    assert body["deployments"][0]["attached_count"] == 1
    assert body["total"] == 1

    async with session_scope() as session:
        stale = (
            await session.exec(
                select(Deployment).where(
                    Deployment.user_id == active_user.id,
                    Deployment.resource_key == "stale-resource",
                )
            )
        ).first()
        assert stale is None


async def test_patch_deployment_history_updates_checkpoint_attachments(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-attachments")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        flow = Flow(
            name=f"flow-{uuid4().hex[:8]}",
            user_id=active_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        flow_history = FlowHistory(
            flow_id=flow.id,
            user_id=active_user.id,
            data={"nodes": [], "edges": []},
            version_number=1,
            description="checkpoint",
        )
        session.add(flow_history)
        await session.flush()

        deployment = Deployment(
            resource_key="deployment-with-attachments",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider["id"]),
            name=f"deployment-attachments-{uuid4().hex[:8]}",
        )
        session.add(deployment)
        await session.flush()
        deployment_id = deployment.resource_key
        history_id = str(flow_history.id)

    adapter = _FakeAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    add_response = await client.patch(
        f"api/v1/deployments/{deployment_id}",
        params={"provider_id": provider["id"]},
        json={"history": {"add": [history_id]}},
        headers=logged_in_headers,
    )
    assert add_response.status_code == status.HTTP_200_OK
    assert adapter.last_update_payload is not None
    assert adapter.last_update_payload.snapshot is not None
    assert adapter.last_update_payload.snapshot.add == ["snapshot-1"]

    async with session_scope() as session:
        attachment = (
            await session.exec(
                select(FlowHistoryDeploymentAttachment).where(
                    FlowHistoryDeploymentAttachment.user_id == active_user.id,
                    FlowHistoryDeploymentAttachment.history_id == UUID(history_id),
                )
            )
        ).first()
        assert attachment is not None
        assert attachment.snapshot_id == "snapshot-1"

    remove_response = await client.patch(
        f"api/v1/deployments/{deployment_id}",
        params={"provider_id": provider["id"]},
        json={"history": {"remove": [history_id]}},
        headers=logged_in_headers,
    )
    assert remove_response.status_code == status.HTTP_200_OK
    assert adapter.last_update_payload is not None
    assert adapter.last_update_payload.snapshot is not None
    assert adapter.last_update_payload.snapshot.remove == ["snapshot-1"]

    async with session_scope() as session:
        attachment = (
            await session.exec(
                select(FlowHistoryDeploymentAttachment).where(
                    FlowHistoryDeploymentAttachment.user_id == active_user.id,
                    FlowHistoryDeploymentAttachment.history_id == UUID(history_id),
                )
            )
        ).first()
        assert attachment is None


async def test_create_deployment_resolves_history_ids_to_raw_history_payloads(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-snapshots")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        flow = Flow(
            name=f"flow-{uuid4().hex[:8]}",
            user_id=active_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()

        checkpoint_data = {"nodes": [{"id": "n1"}], "edges": []}
        flow_history = FlowHistory(
            flow_id=flow.id,
            user_id=active_user.id,
            data=checkpoint_data,
            version_number=1,
            description="checkpoint-for-create",
        )
        session.add(flow_history)
        await session.flush()

        history_id = str(flow_history.id)
        flow_id = str(flow.id)
        folder_id = str(folder.id)
        flow_name = flow.name

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment with checkpoint references",
                "type": "agent",
            },
            "history": {
                "artifact_type": "flow",
                "reference_ids": [history_id],
            },
            "project_id": folder_id,
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert capture_adapter.received_payload is not None
    assert capture_adapter.received_payload.snapshot is not None
    assert capture_adapter.received_payload.snapshot.reference_ids is None
    assert capture_adapter.received_payload.snapshot.raw_payloads is not None
    assert len(capture_adapter.received_payload.snapshot.raw_payloads) == 1
    raw_payload = capture_adapter.received_payload.snapshot.raw_payloads[0]
    assert str(raw_payload.id) == flow_id
    assert raw_payload.name == flow_name
    assert raw_payload.data == checkpoint_data
    assert raw_payload.provider_data == {"project_id": folder_id}

    async with session_scope() as session:
        attachment = (
            await session.exec(
                select(FlowHistoryDeploymentAttachment).where(
                    FlowHistoryDeploymentAttachment.user_id == active_user.id,
                    FlowHistoryDeploymentAttachment.history_id == UUID(history_id),
                )
            )
        ).first()
        assert attachment is not None
        assert attachment.snapshot_id == "provider-snapshot-1"


async def test_create_deployment_rejects_history_references_from_other_project_when_project_id_is_explicit(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-project-scope-explicit")

    async with session_scope() as session:
        target_folder = Folder(name=f"proj-target-{uuid4().hex[:8]}", user_id=active_user.id)
        other_folder = Folder(name=f"proj-other-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(target_folder)
        session.add(other_folder)
        await session.flush()

        other_flow = Flow(
            name=f"flow-other-{uuid4().hex[:8]}",
            user_id=active_user.id,
            folder_id=other_folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(other_flow)
        await session.flush()

        other_flow_history = FlowHistory(
            flow_id=other_flow.id,
            user_id=active_user.id,
            data={"nodes": [{"id": "n1"}], "edges": []},
            version_number=1,
            description="checkpoint-from-other-project",
        )
        session.add(other_flow_history)
        await session.flush()

        target_project_id = str(target_folder.id)
        history_id = str(other_flow_history.id)

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment with explicit project mismatch",
                "type": "agent",
            },
            "project_id": target_project_id,
            "history": {
                "artifact_type": "flow",
                "reference_ids": [history_id],
            },
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert capture_adapter.received_payload is None


async def test_create_deployment_rejects_history_references_not_in_default_project_when_project_id_is_missing(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-project-scope-default")

    async with session_scope() as session:
        non_default_folder = Folder(name=f"proj-non-default-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(non_default_folder)
        await session.flush()

        flow = Flow(
            name=f"flow-non-default-{uuid4().hex[:8]}",
            user_id=active_user.id,
            folder_id=non_default_folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()

        flow_history = FlowHistory(
            flow_id=flow.id,
            user_id=active_user.id,
            data={"nodes": [{"id": "n1"}], "edges": []},
            version_number=1,
            description="checkpoint-outside-default-project",
        )
        session.add(flow_history)
        await session.flush()

        history_id = str(flow_history.id)

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment defaults to starter project",
                "type": "agent",
            },
            "history": {
                "artifact_type": "flow",
                "reference_ids": [history_id],
            },
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert capture_adapter.received_payload is None


async def test_create_deployment_falls_back_to_default_project_when_project_id_is_missing(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-default-project-fallback")

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment without explicit project id",
                "type": "agent",
            }
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert capture_adapter.received_payload is not None

    async with session_scope() as session:
        default_folder = (
            await session.exec(
                select(Folder).where(
                    Folder.user_id == active_user.id,
                    Folder.name == DEFAULT_FOLDER_NAME,
                )
            )
        ).first()
        assert default_folder is not None

        deployment_row = (
            await session.exec(
                select(Deployment).where(
                    Deployment.user_id == active_user.id,
                    Deployment.resource_key == "provider-deployment-1",
                )
            )
        ).first()
        assert deployment_row is not None
        assert deployment_row.project_id == default_folder.id

    assert capture_adapter.received_payload.project_id == default_folder.id


async def test_create_deployment_uses_explicit_project_id_from_request(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-explicit-project")

    async with session_scope() as session:
        target_folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(target_folder)
        await session.flush()
        target_project_id = target_folder.id

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment with explicit project id",
                "type": "agent",
            },
            "project_id": str(target_project_id),
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert capture_adapter.received_payload is not None
    assert capture_adapter.received_payload.project_id == target_project_id

    async with session_scope() as session:
        deployment_row = (
            await session.exec(
                select(Deployment).where(
                    Deployment.user_id == active_user.id,
                    Deployment.resource_key == "provider-deployment-1",
                )
            )
        ).first()
        assert deployment_row is not None
        assert deployment_row.project_id == target_project_id


async def test_create_deployment_accepts_history_raw_payloads_from_api(client, logged_in_headers, monkeypatch):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-raw-payload-reject")

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        params={"provider_id": provider["id"]},
        json={
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "raw payload should be accepted",
                "type": "agent",
            },
            "history": {
                "artifact_type": "flow",
                "raw_payloads": [
                    {
                        "id": str(uuid4()),
                        "name": "flow-from-client",
                        "description": "raw payload from client",
                        "data": {"nodes": [], "edges": []},
                        "provider_data": {"project_id": str(uuid4())},
                    }
                ],
            },
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert capture_adapter.received_payload is not None
    assert capture_adapter.received_payload.snapshot is not None
    assert capture_adapter.received_payload.snapshot.raw_payloads is not None
    assert len(capture_adapter.received_payload.snapshot.raw_payloads) == 1
    raw_payload = capture_adapter.received_payload.snapshot.raw_payloads[0]
    assert isinstance(raw_payload.provider_data, dict)
    assert "project_id" in raw_payload.provider_data


async def test_detect_deployment_environment_variables_from_secret_template_fields(
    client, logged_in_headers, active_user
):
    async with session_scope() as session:
        flow_history = FlowHistory(
            flow_id=uuid4(),
            user_id=active_user.id,
            data={
                "nodes": [
                    {
                        "data": {
                            "node": {
                                "template": {
                                    "openai_api_key": {
                                        "type": "SecretStr",
                                        "password": True,
                                        "load_from_db": True,
                                        "show": True,
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            version_number=1,
            description="checkpoint-with-secret-template-field",
        )
        session.add(flow_history)
        await session.flush()
        history_id = str(flow_history.id)

    response = await client.post(
        "api/v1/deployments/variables/detections",
        json={"reference_ids": [history_id]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["variables"] == []


async def test_detect_deployment_environment_variables_includes_valid_global_variable_binding(
    client, logged_in_headers, active_user
):
    async with session_scope() as session:
        session.add(
            Variable(
                name="OPENAI_API_KEY",
                value="dummy",
                user_id=active_user.id,
                type="generic",
                default_fields=[],
            )
        )
        flow_history = FlowHistory(
            flow_id=uuid4(),
            user_id=active_user.id,
            data={
                "nodes": [
                    {
                        "data": {
                            "node": {
                                "template": {
                                    "api_key": {
                                        "name": "api_key",
                                        "type": "SecretStr",
                                        "password": True,
                                        "load_from_db": True,
                                        "value": "OPENAI_API_KEY",
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            version_number=1,
            description="checkpoint-with-load-from-db-binding",
        )
        session.add(flow_history)
        await session.flush()
        history_id = str(flow_history.id)

    response = await client.post(
        "api/v1/deployments/variables/detections",
        json={"reference_ids": [history_id]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["variables"] == [{"key": "api_key", "global_variable_name": "OPENAI_API_KEY"}]


async def test_list_snapshots_endpoint_is_available(client, logged_in_headers, monkeypatch):
    provider = await _create_provider(client, logged_in_headers, "tenant-snapshots-list")
    adapter = _ConfigsAndSnapshotsAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.get(
        "api/v1/deployments/snapshots",
        params={"provider_id": provider["id"], "artifact_type": "flow"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["artifact_type"] == "flow"
    assert response.json()["snapshots"] == []
    assert adapter.last_artifact_type == ArtifactType.FLOW


async def test_deployment_config_endpoints_crud_cycle(client, logged_in_headers, monkeypatch):
    provider = await _create_provider(client, logged_in_headers, "tenant-config-crud")
    adapter = _ConfigsAndSnapshotsAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    create_response = await client.post(
        "api/v1/deployments/configs",
        params={"provider_id": provider["id"]},
        json={
            "name": "test-config",
            "description": "config for endpoint restore test",
            "environment_variables": {},
        },
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["id"] == "cfg-created"
    assert adapter.created_config is not None
    assert adapter.created_config.name == "test-config"

    list_response = await client.get(
        "api/v1/deployments/configs",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()["configs"]) == 1
    assert list_response.json()["configs"][0]["id"] == "cfg-listed"

    get_response = await client.get(
        "api/v1/deployments/configs/cfg-listed",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["id"] == "cfg-listed"

    patch_response = await client.patch(
        "api/v1/deployments/configs/cfg-listed",
        params={"provider_id": provider["id"]},
        json={"name": "updated-config"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["id"] == "cfg-listed"
    assert adapter.updated_config is not None
    assert adapter.updated_config[0] == "cfg-listed"
    assert adapter.updated_config[1].name == "updated-config"

    delete_response = await client.delete(
        "api/v1/deployments/configs/cfg-listed",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert adapter.deleted_config_id == "cfg-listed"
