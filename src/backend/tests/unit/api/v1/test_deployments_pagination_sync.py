from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import status
from langflow.api.v1 import deployment as deployment_api
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.flow_history_deployment_attachment.model import (
    FlowHistoryDeploymentAttachment,
)
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult,
    DeploymentListResult,
    DeploymentType,
    DeploymentUpdateResult,
    ItemResult,
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

    async def list(self, *, params=None, **_):
        provider_params = params.provider_params if params else None
        ids = provider_params.get("ids", []) if isinstance(provider_params, dict) else []
        requested_types = params.deployment_types if params else None
        resolved_type = requested_types[0] if requested_types else DeploymentType.AGENT
        kept = []
        if "keep-resource" in ids:
            kept.append(
                ItemResult(
                    id="keep-resource",
                    name="Keep Deployment",
                    type=resolved_type,
                )
            )
        return DeploymentListResult(deployments=kept)

    async def update(self, *, deployment_id, **_) -> DeploymentUpdateResult:
        self.last_update_payload = _.get("payload")
        return DeploymentUpdateResult(id=deployment_id)

    async def materialize_snapshots(self, *, raw_payloads, **_) -> list[str]:
        return [f"snapshot-{idx}" for idx, _ in enumerate(raw_payloads, start=1)]


class _EchoAdapter:
    async def list(self, *, params=None, **_):
        provider_params = params.provider_params if params else {}
        ids = provider_params.get("ids", []) if isinstance(provider_params, dict) else []
        requested_types = params.deployment_types if params else None
        resolved_type = requested_types[0] if requested_types else DeploymentType.AGENT
        return DeploymentListResult(
            deployments=[
                ItemResult(id=resource_id, name=f"deployment-{resource_id}", type=resolved_type) for resource_id in ids
            ],
        )

    async def update(self, *, deployment_id, **_) -> DeploymentUpdateResult:
        return DeploymentUpdateResult(id=deployment_id)

    async def materialize_snapshots(self, *, raw_payloads, **_) -> list[str]:
        return [f"snapshot-{idx}" for idx, _ in enumerate(raw_payloads, start=1)]


class _CreateCaptureAdapter:
    def __init__(self) -> None:
        self.received_payload = None

    async def create(self, *, payload, **_) -> DeploymentCreateResult:
        self.received_payload = payload
        return DeploymentCreateResult(
            id="provider-deployment-1",
            snapshot_ids=["provider-snapshot-1"],
            name=payload.spec.name,
            description=payload.spec.description,
            type=payload.spec.type,
        )


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


async def test_list_deployments_filters_by_history_ids_and_exposes_matched_ids(
    client, logged_in_headers, active_user, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-history-filter")

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

        history_rows: list[FlowHistory] = []
        for version_number in range(1, 4):
            row = FlowHistory(
                flow_id=flow.id,
                user_id=active_user.id,
                data={"nodes": [], "edges": []},
                version_number=version_number,
                description=f"checkpoint-{version_number}",
            )
            session.add(row)
            history_rows.append(row)
        await session.flush()

        deployment_one = Deployment(
            resource_key="history-filter-1",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider["id"]),
            name=f"deployment-one-{uuid4().hex[:8]}",
        )
        deployment_two = Deployment(
            resource_key="history-filter-2",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider["id"]),
            name=f"deployment-two-{uuid4().hex[:8]}",
        )
        deployment_three = Deployment(
            resource_key="history-filter-3",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider["id"]),
            name=f"deployment-three-{uuid4().hex[:8]}",
        )
        session.add(deployment_one)
        session.add(deployment_two)
        session.add(deployment_three)
        await session.flush()

        session.add(
            FlowHistoryDeploymentAttachment(
                user_id=active_user.id,
                history_id=history_rows[0].id,
                deployment_id=deployment_one.id,
            )
        )
        session.add(
            FlowHistoryDeploymentAttachment(
                user_id=active_user.id,
                history_id=history_rows[1].id,
                deployment_id=deployment_two.id,
            )
        )
        session.add(
            FlowHistoryDeploymentAttachment(
                user_id=active_user.id,
                history_id=history_rows[2].id,
                deployment_id=deployment_three.id,
            )
        )
        await session.flush()

        history_id_one = str(history_rows[0].id)
        history_id_two = str(history_rows[1].id)

    async def _mock_resolve_adapter(*_, **__):
        return _EchoAdapter()

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.get(
        "api/v1/deployments",
        params={
            "provider_id": provider["id"],
            "page": 1,
            "size": 10,
            "history_ids": [history_id_one, history_id_two],
            "match_limit": 1,
        },
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    # OR-style matching across history_ids with optional match_limit cap.
    assert body["total"] == 2
    assert len(body["deployments"]) == 1
    matched_history_ids = body["deployments"][0]["provider_data"]["matched_history_ids"]
    assert set(matched_history_ids).issubset({history_id_one, history_id_two})


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
        deployment_id = str(deployment.id)
        history_id = str(flow_history.id)

    adapter = _FakeAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    add_response = await client.patch(
        f"api/v1/deployments/{deployment_id}",
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
        json={
            "provider_id": provider["id"],
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment with checkpoint references",
                "type": "agent",
            },
            "flow_versions": {
                "ids": [history_id],
            },
            "project_id": folder_id,
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert capture_adapter.received_payload is not None
    assert capture_adapter.received_payload.snapshot is not None
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
        json={
            "provider_id": provider["id"],
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment with explicit project mismatch",
                "type": "agent",
            },
            "project_id": target_project_id,
            "flow_versions": {
                "ids": [history_id],
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
        json={
            "provider_id": provider["id"],
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment defaults to starter project",
                "type": "agent",
            },
            "flow_versions": {
                "ids": [history_id],
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
        json={
            "provider_id": provider["id"],
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "deployment without explicit project id",
                "type": "agent",
            },
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

    assert capture_adapter.received_payload.snapshot is None


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
        json={
            "provider_id": provider["id"],
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
    assert capture_adapter.received_payload.snapshot is None

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


async def test_create_deployment_rejects_history_raw_payloads_from_api(client, logged_in_headers, monkeypatch):
    provider = await _create_provider(client, logged_in_headers, "tenant-create-raw-payload-reject")

    capture_adapter = _CreateCaptureAdapter()

    async def _mock_resolve_adapter(*_, **__):
        return capture_adapter

    monkeypatch.setattr(deployment_api, "_resolve_deployment_adapter", _mock_resolve_adapter)

    response = await client.post(
        "api/v1/deployments",
        json={
            "provider_id": provider["id"],
            "spec": {
                "name": f"deployment-{uuid4().hex[:8]}",
                "description": "raw payload should be rejected",
                "type": "agent",
            },
            "flow_versions": {
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

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert capture_adapter.received_payload is None


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


async def test_snapshot_and_config_endpoints_are_removed(client, logged_in_headers):
    provider = await _create_provider(client, logged_in_headers, "tenant-removed-routes")

    snapshot_response = await client.get(
        "api/v1/deployments/snapshots",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert snapshot_response.status_code == status.HTTP_404_NOT_FOUND

    config_response = await client.get(
        "api/v1/deployments/configs",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert config_response.status_code == status.HTTP_404_NOT_FOUND


async def test_list_deployment_types_rejects_provider_account_without_provider_key(
    client, logged_in_headers, monkeypatch
):
    provider = await _create_provider(client, logged_in_headers, "tenant-empty-provider-key")

    async with session_scope() as session:
        provider_row = (
            await session.exec(
                select(DeploymentProviderAccount).where(
                    DeploymentProviderAccount.id == UUID(provider["id"]),
                )
            )
        ).first()
        assert provider_row is not None
        provider_row.provider_key = "   "
        session.add(provider_row)

    # Prevent unrelated import side effects for this path.
    monkeypatch.setattr(deployment_api, "_ensure_builtin_deployment_adapter_loaded", lambda *_: None)

    response = await client.get(
        "api/v1/deployments/types",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "provider_key" in response.json()["detail"]


async def test_list_deployment_types_rejects_unregistered_provider_adapter(client, logged_in_headers, monkeypatch):
    create_response = await client.post(
        "api/v1/deployments/providers/",
        json=_provider_payload(account_id="tenant-missing-adapter", provider_key="missing-adapter"),
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    provider = create_response.json()

    monkeypatch.setattr(deployment_api, "_ensure_builtin_deployment_adapter_loaded", lambda *_: None)

    response = await client.get(
        "api/v1/deployments/types",
        params={"provider_id": provider["id"]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No deployment adapter registered" in response.json()["detail"]


async def test_create_execution_rejects_deployment_provider_mismatch(client, logged_in_headers, active_user):
    provider_a = await _create_provider(client, logged_in_headers, "tenant-exec-provider-a")
    provider_b = await _create_provider(client, logged_in_headers, "tenant-exec-provider-b")

    async with session_scope() as session:
        folder = Folder(name=f"proj-{uuid4().hex[:8]}", user_id=active_user.id)
        session.add(folder)
        await session.flush()

        deployment = Deployment(
            resource_key="provider-a-resource",
            user_id=active_user.id,
            project_id=folder.id,
            provider_account_id=UUID(provider_a["id"]),
            name=f"deployment-provider-a-{uuid4().hex[:8]}",
        )
        session.add(deployment)
        await session.flush()
        deployment_id = str(deployment.id)

    response = await client.post(
        "api/v1/deployments/executions",
        json={
            "provider_id": provider_b["id"],
            "deployment_id": deployment_id,
            "deployment_type": "agent",
            "input": "hello",
        },
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Deployment not found for provider."
