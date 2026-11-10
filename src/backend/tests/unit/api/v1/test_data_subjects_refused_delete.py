"""A deletion an administrator starts and a guard refuses must leave nothing that can be approved later."""

from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.auth.authz import AuthzAuditLog
from langflow.services.database.models.data_subject_request import DataSubjectRequest
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.services.adapters.deployment.schema import DeploymentType
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import col, select

from tests.unit.services.data_subjects._seed import create_user


async def _deploy_for(user_id: UUID) -> None:
    suffix = uuid4().hex[:8]
    async with session_scope() as session:
        folder = Folder(name=f"project-{suffix}", user_id=user_id)
        provider = DeploymentProviderAccount(
            user_id=user_id,
            name=f"provider-{suffix}",
            provider_tenant_id="tenant-1",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url=f"https://provider-{suffix}.example.com",
            api_key="encrypted-value",  # pragma: allowlist secret
        )
        session.add_all([folder, provider])
        await session.flush()
        session.add(
            Deployment(
                user_id=user_id,
                project_id=folder.id,
                deployment_provider_account_id=provider.id,
                resource_key=f"rk-{suffix}",
                display_name=f"deployment-{suffix}",
                deployment_type=DeploymentType.AGENT,
            )
        )


async def _requests_for(user_id: UUID) -> list[DataSubjectRequest]:
    async with session_scope() as session:
        return list(
            (await session.exec(select(DataSubjectRequest).where(DataSubjectRequest.subject_user_id == user_id))).all()
        )


async def _dsar_events_for(request_ids: list[UUID]) -> list[str]:
    async with session_scope() as session:
        rows = await session.exec(
            select(AuthzAuditLog.action).where(
                col(AuthzAuditLog.action).startswith("dsar:"), col(AuthzAuditLog.resource_id).in_(request_ids)
            )
        )
        return list(rows.all())


@pytest.mark.parametrize("flag_on", [True, False], ids=["flag-on", "flag-off"])
async def test_should_leave_no_request_when_admin_delete_is_refused(
    client: AsyncClient, logged_in_headers_super_user, monkeypatch, flag_on
):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", flag_on)
    user_id = await create_user(f"deployed-{uuid4().hex[:8]}")
    await _deploy_for(user_id)

    response = await client.delete(f"api/v1/users/{user_id}", headers=logged_in_headers_super_user)

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert response.json()["detail"]["code"] == "deployed_flows"
    assert await _requests_for(user_id) == []


async def test_should_leave_no_request_when_direct_erase_is_refused(
    client: AsyncClient, logged_in_headers_super_user, monkeypatch
):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", True)
    user_id = await create_user(f"deployed-{uuid4().hex[:8]}")
    await _deploy_for(user_id)

    response = await client.post(
        "api/v1/data-subjects/erase",
        json={"subject_type": "builder", "user_id": str(user_id)},
        headers=logged_in_headers_super_user,
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert await _requests_for(user_id) == []


async def test_should_keep_the_builders_own_request_when_admin_delete_is_refused(
    client: AsyncClient, logged_in_headers_super_user, monkeypatch
):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", True)
    username = f"deployed-{uuid4().hex[:8]}"
    user_id = await create_user(username)
    credentials = {"username": username, "password": "test-password-123"}  # pragma: allowlist secret
    login = await client.post("api/v1/login", data=credentials)
    builder_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    asked = await client.post("api/v1/users/me/deletion-request", headers=builder_headers)
    assert asked.status_code == status.HTTP_201_CREATED, asked.text
    await _deploy_for(user_id)

    response = await client.delete(f"api/v1/users/{user_id}", headers=logged_in_headers_super_user)

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    requests = await _requests_for(user_id)
    assert [request.status for request in requests] == ["requested"]
    assert sorted(await _dsar_events_for([requests[0].id])) == ["dsar:approve", "dsar:request"]
