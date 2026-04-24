from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v1.mappers.deployments.contracts import ProviderSnapshotBinding
from langflow.services.database.models.deployment.crud import create_deployment
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.crud import create_provider_account
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    create_deployment_attachment,
    delete_deployment_attachments_by_keys,
    delete_unbound_attachments,
    list_attachments_by_deployment_ids,
    update_deployment_attachment_provider_snapshot_id,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import FlowVersionDeploymentAttachment
from langflow.services.database.models.flow_version_deployment_attachment.schema import (
    DeploymentAttachmentKeyBatch,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from lfx.services.adapters.deployment.schema import DeploymentType

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


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

        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            provider_account_id=provider_account_id,
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
            provider_snapshot_id="tool-2",
        )
        keep_null = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[2],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-3",
        )

        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            provider_account_id=provider_account_id,
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
            provider_account_id=uuid4(),
            deployment_ids=[],
            bindings=[ProviderSnapshotBinding(resource_key="agent-1", snapshot_id="tool-1")],
        )
    assert deleted_count == 0


@pytest.mark.asyncio
async def test_delete_unbound_attachments_drops_deployments_outside_provider_scope(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id, count=1)
    provider_account_id_a = await _create_provider_account(user_id=active_user.id)
    provider_account_id_b = await _create_provider_account(user_id=active_user.id)

    async with session_scope() as session:
        dep_a = await create_deployment(
            session,
            user_id=active_user.id,
            project_id=folder_id,
            deployment_provider_account_id=provider_account_id_a,
            resource_key="shared-resource",
            name=f"dep-a-{uuid4()}",
            deployment_type=DeploymentType.AGENT,
        )
        dep_b = await create_deployment(
            session,
            user_id=active_user.id,
            project_id=folder_id,
            deployment_provider_account_id=provider_account_id_b,
            resource_key="shared-resource",
            name=f"dep-b-{uuid4()}",
            deployment_type=DeploymentType.AGENT,
        )
        scoped_attachment = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep_a.id,
            provider_snapshot_id="tool-1",
        )
        out_of_scope_attachment = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep_b.id,
            provider_snapshot_id="tool-2",
        )

        deleted_count = await delete_unbound_attachments(
            session,
            user_id=active_user.id,
            provider_account_id=provider_account_id_a,
            deployment_ids=[dep_a.id, dep_b.id],
            bindings=[],
        )
        remaining = await list_attachments_by_deployment_ids(
            session,
            user_id=active_user.id,
            deployment_ids=[dep_a.id, dep_b.id],
        )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 1
    assert scoped_attachment.id not in remaining_ids
    assert out_of_scope_attachment.id in remaining_ids


@pytest.mark.asyncio
async def test_delete_unbound_attachments_in_memory_sqlite_coverage(async_session: AsyncSession):
    user = User(
        username=f"user-{uuid4()}",
        password="hashed-password",  # noqa: S106  # pragma: allowlist secret
        is_active=True,
        is_superuser=False,
    )
    async_session.add(user)
    await async_session.flush()

    folder = Folder(name=f"project-{uuid4()}", description=None, user_id=user.id)
    async_session.add(folder)
    await async_session.flush()

    flow = Flow(
        name=f"flow-{uuid4()}",
        data={"nodes": [], "edges": []},
        user_id=user.id,
        folder_id=folder.id,
        is_component=False,
    )
    async_session.add(flow)
    await async_session.flush()

    flow_version = FlowVersion(
        flow_id=flow.id,
        user_id=user.id,
        data={"nodes": [], "edges": []},
        version_number=1,
    )
    async_session.add(flow_version)
    await async_session.flush()

    provider_account_a = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id=None,
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        name=f"provider-a-{uuid4()}",
        provider_url="https://test-a.example.com",
        api_key="test-key-a",  # pragma: allowlist secret
    )
    provider_account_b = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id=None,
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        name=f"provider-b-{uuid4()}",
        provider_url="https://test-b.example.com",
        api_key="test-key-b",  # pragma: allowlist secret
    )
    async_session.add(provider_account_a)
    async_session.add(provider_account_b)
    await async_session.flush()

    deployment_a = Deployment(
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account_a.id,
        resource_key="shared-resource",
        name=f"dep-a-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )
    deployment_b = Deployment(
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account_b.id,
        resource_key="shared-resource",
        name=f"dep-b-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )
    async_session.add(deployment_a)
    async_session.add(deployment_b)
    await async_session.flush()

    attachment_a = FlowVersionDeploymentAttachment(
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment_a.id,
        provider_snapshot_id="tool-1",
    )
    attachment_b = FlowVersionDeploymentAttachment(
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment_b.id,
        provider_snapshot_id="tool-2",
    )
    async_session.add(attachment_a)
    async_session.add(attachment_b)
    await async_session.flush()

    deleted_count = await delete_unbound_attachments(
        async_session,
        user_id=user.id,
        provider_account_id=provider_account_a.id,
        deployment_ids=[deployment_a.id, deployment_b.id],
        bindings=[],
    )
    remaining = await list_attachments_by_deployment_ids(
        async_session,
        user_id=user.id,
        deployment_ids=[deployment_a.id, deployment_b.id],
    )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 1
    assert attachment_a.id not in remaining_ids
    assert attachment_b.id in remaining_ids


@pytest.mark.asyncio
async def test_create_deployment_attachment_rejects_falsy_snapshot_id(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id, count=1)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, _dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        with pytest.raises(ValueError, match="provider_snapshot_id must not be empty"):
            await create_deployment_attachment(
                session,
                user_id=active_user.id,
                flow_version_id=version_ids[0],
                deployment_id=dep1_id,
                provider_snapshot_id=None,  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError, match="provider_snapshot_id must not be empty"):
            await create_deployment_attachment(
                session,
                user_id=active_user.id,
                flow_version_id=version_ids[0],
                deployment_id=dep1_id,
                provider_snapshot_id="   ",
            )


@pytest.mark.asyncio
async def test_update_deployment_attachment_rejects_falsy_snapshot_id(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id, count=1)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, _dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        attachment = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-1",
        )
        with pytest.raises(ValueError, match="provider_snapshot_id must not be empty"):
            await update_deployment_attachment_provider_snapshot_id(
                session,
                attachment=attachment,
                provider_snapshot_id="",
            )


@pytest.mark.asyncio
async def test_delete_deployment_attachments_by_keys_removes_exact_rows(active_user: User):
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        dep1_stale = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-stale",
        )
        dep1_keep = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[1],
            deployment_id=dep1_id,
            provider_snapshot_id="tool-keep",
        )
        dep2_keep = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[2],
            deployment_id=dep2_id,
            provider_snapshot_id="tool-keep-dep2",
        )

        deleted_count = await delete_deployment_attachments_by_keys(
            session,
            user_id=active_user.id,
            attachment_key_batch=DeploymentAttachmentKeyBatch(
                keys=[
                    {
                        "deployment_id": dep1_id,
                        "flow_version_id": version_ids[0],
                    }
                ]
            ),
        )
        remaining = await list_attachments_by_deployment_ids(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id, dep2_id],
        )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 1
    assert dep1_stale.id not in remaining_ids
    assert dep1_keep.id in remaining_ids
    assert dep2_keep.id in remaining_ids


@pytest.mark.asyncio
async def test_delete_deployment_attachments_by_keys_avoids_cartesian_cross_delete(active_user: User):
    """Regression: only exact keys are deleted, not deployment_id x flow_version_id combinations."""
    folder_id = await _create_folder(user_id=active_user.id)
    version_ids = await _create_flow_versions(user_id=active_user.id, folder_id=folder_id, count=4)
    provider_account_id = await _create_provider_account(user_id=active_user.id)
    dep1_id, dep2_id = await _create_deployments(
        user_id=active_user.id,
        folder_id=folder_id,
        provider_account_id=provider_account_id,
    )

    async with session_scope() as session:
        dep1_target = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep1_id,
            provider_snapshot_id="snap-a",
        )
        dep2_target = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[1],
            deployment_id=dep2_id,
            provider_snapshot_id="snap-b",
        )
        dep1_cross = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[1],
            deployment_id=dep1_id,
            provider_snapshot_id="snap-cross-1",
        )
        dep2_cross = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[0],
            deployment_id=dep2_id,
            provider_snapshot_id="snap-cross-2",
        )
        dep1_keep = await create_deployment_attachment(
            session,
            user_id=active_user.id,
            flow_version_id=version_ids[2],
            deployment_id=dep1_id,
            provider_snapshot_id="snap-keep",
        )

        deleted_count = await delete_deployment_attachments_by_keys(
            session,
            user_id=active_user.id,
            attachment_key_batch=DeploymentAttachmentKeyBatch(
                keys=[
                    {"deployment_id": dep1_id, "flow_version_id": version_ids[0]},
                    {"deployment_id": dep2_id, "flow_version_id": version_ids[1]},
                ]
            ),
        )
        remaining = await list_attachments_by_deployment_ids(
            session,
            user_id=active_user.id,
            deployment_ids=[dep1_id, dep2_id],
        )

    remaining_ids = {row.id for row in remaining}
    assert deleted_count == 2
    assert dep1_target.id not in remaining_ids
    assert dep2_target.id not in remaining_ids
    assert dep1_cross.id in remaining_ids
    assert dep2_cross.id in remaining_ids
    assert dep1_keep.id in remaining_ids
