from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v1.mappers.deployments.contracts import ProviderSnapshotBinding
from langflow.services.database.models.deployment.crud import create_deployment
from langflow.services.database.models.deployment_provider_account.crud import create_provider_account
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    create_deployment_attachment,
    delete_unbound_attachments,
    list_attachments_by_deployment_ids,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.services.adapters.deployment.schema import DeploymentType

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


async def _create_folder(*, user_id):
    async with session_scope() as session:
        folder = Folder(name=f"project-{uuid4()}", description=None, user_id=user_id)
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        return folder.id


async def _create_flow_versions(*, user_id, folder_id, count: int = 3):
    async with session_scope() as session:
        flow = Flow(
            name=f"flow-{uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=user_id,
            folder_id=folder_id,
            is_component=False,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)

        versions: list[FlowVersion] = []
        for index in range(1, count + 1):
            version = FlowVersion(
                flow_id=flow.id,
                user_id=user_id,
                data={"nodes": [], "edges": []},
                version_number=index,
            )
            session.add(version)
            versions.append(version)
        await session.flush()
        for version in versions:
            await session.refresh(version)
        return [version.id for version in versions]


async def _create_provider_account(*, user_id):
    async with session_scope() as session:
        provider_account = await create_provider_account(
            session,
            user_id=user_id,
            name=f"provider-{uuid4()}",
            provider_tenant_id=None,
            provider_key="watsonx-orchestrate",
            provider_url="https://test.example.com",
            api_key="test-key",  # pragma: allowlist secret
        )
        return provider_account.id


async def _create_deployments(*, user_id, folder_id, provider_account_id):
    async with session_scope() as session:
        dep1 = await create_deployment(
            session,
            user_id=user_id,
            project_id=folder_id,
            deployment_provider_account_id=provider_account_id,
            resource_key="agent-1",
            name=f"dep-1-{uuid4()}",
            deployment_type=DeploymentType.AGENT,
        )
        dep2 = await create_deployment(
            session,
            user_id=user_id,
            project_id=folder_id,
            deployment_provider_account_id=provider_account_id,
            resource_key="agent-2",
            name=f"dep-2-{uuid4()}",
            deployment_type=DeploymentType.AGENT,
        )
        return dep1.id, dep2.id


@pytest.mark.asyncio
async def test_delete_unbound_attachments_keeps_matching_bindings(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        keep_dep1 = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-1",
        )
        stale_dep1 = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[1],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-stale",
        )
        keep_dep2 = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[2],
            deployment_id=dep2_id,
            provider_snapshot_id="tool-2",
        )
        keep_empty = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep2_id,
            provider_snapshot_id=None,
        )

        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id, dep2_id],
            bindings=[
                ProviderSnapshotBinding(resource_key="agent-1", snapshot_id="tool-1"),
                ProviderSnapshotBinding(resource_key="agent-2", snapshot_id="tool-2"),
            ],
        )
        remaining = await list_attachments_by_deployment_ids(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id, dep2_id],
        )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 1
    assert keep_dep1.id in remaining_ids
    assert keep_dep2.id in remaining_ids
    assert keep_empty.id in remaining_ids
    assert stale_dep1.id not in remaining_ids


@pytest.mark.asyncio
async def test_delete_unbound_attachments_empty_bindings_deletes_all_attachments(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, _dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        stale_a = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-1",
        )
        keep_empty_str = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[1],
            deployment_id=dep1_id,
            provider_snapshot_id="",
        )
        keep_null = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[2],
            deployment_id=dep1_id,
            provider_snapshot_id=None,
        )

        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id],
            bindings=[],
        )
        remaining = await list_attachments_by_deployment_ids(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id],
        )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 3
    assert stale_a.id not in remaining_ids
    assert keep_empty_str.id not in remaining_ids
    assert keep_null.id not in remaining_ids


@pytest.mark.asyncio
async def test_delete_unbound_attachments_empty_deployment_ids_noop(active_user: User):
    async with session_scope() as session:
        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            deployment_ids=[],
            bindings=[ProviderSnapshotBinding(resource_key="agent-1", snapshot_id="tool-1")],
        )
    assert deleted_count == 0
