"""Deployment authorization tests for project-scoped flow-version references."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from ._common import _StubAuthorizationService, install_audit_recorder, install_authz, install_settings


class _RowsResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _RowsSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    async def exec(self, _statement):
        return _RowsResult(self._rows)


class _DeploymentPolicyAuthz(_StubAuthorizationService):
    def __init__(self, *, allowed_flow_ids: set[UUID]) -> None:
        super().__init__(allow=False)
        self.allowed_flow_ids = allowed_flow_ids

    async def supports_cross_user_fetch(self) -> bool:
        return True

    async def is_enabled(self) -> bool:
        return True

    async def enforce(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return kwargs["act"] == "deploy" and UUID(kwargs["obj"].split(":", 1)[1]) in self.allowed_flow_ids


class _AdminDeploymentAuthz(_DeploymentPolicyAuthz):
    def __init__(self, *, allowed_project_ids: set[UUID]) -> None:
        super().__init__(allowed_flow_ids=set())
        self.allowed_project_ids = allowed_project_ids

    async def enforce(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        if kwargs["act"] == "read" and kwargs["obj"].startswith("project:"):
            return UUID(kwargs["obj"].split(":", 1)[1]) in self.allowed_project_ids
        return kwargs["act"] == "create" and kwargs["obj"] == "deployment:*"


def _flow_version_row(*, project_id: UUID, owner_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        flow_version_id=uuid4(),
        flow_id=uuid4(),
        flow_user_id=owner_id or uuid4(),
        workspace_id=uuid4(),
        folder_id=project_id,
    )


def _install_deployment_authz(monkeypatch, service: _DeploymentPolicyAuthz) -> None:
    from langflow.services.authorization import deployment as deployment_authz

    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)
    monkeypatch.setattr(deployment_authz, "get_authorization_service", lambda: service)


@pytest.mark.anyio
async def test_shared_project_resolution_uses_real_owner_and_domain(monkeypatch, async_session):
    """An admin can target a foreign project without losing its authorization context."""
    from langflow.services.authorization.deployment import resolve_project_id_for_deployment_create
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User

    actor = User(username=f"actor-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    owner = User(username=f"owner-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    async_session.add(actor)
    async_session.add(owner)
    await async_session.flush()
    project = Folder(name=f"project-{uuid4()}", user_id=owner.id, workspace_id=uuid4())
    async_session.add(project)
    await async_session.flush()

    service = _AdminDeploymentAuthz(allowed_project_ids={project.id})
    _install_deployment_authz(monkeypatch, service)

    resolved = await resolve_project_id_for_deployment_create(
        session=async_session,
        current_user=actor,
        requested_project_id=project.id,
    )

    assert resolved == project.id
    project_call, deployment_call = service.calls
    assert project_call["domain"] == f"workspace:{project.workspace_id}"
    assert project_call["obj"] == f"project:{project.id}"
    assert project_call["context"]["project_user_id"] == owner.id
    assert deployment_call["domain"] == f"project:{project.id}"
    assert deployment_call["obj"] == "deployment:*"
    assert deployment_call["act"] == "create"
    assert deployment_call["context"]["deployment_user_id"] == actor.id


@pytest.mark.anyio
async def test_shared_project_resolution_maps_permission_denial_to_404(monkeypatch, async_session):
    """A denied foreign project is indistinguishable from an unknown UUID."""
    from langflow.services.authorization.deployment import resolve_project_id_for_deployment_create
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User

    actor = User(username=f"actor-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    owner = User(username=f"owner-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    async_session.add(actor)
    async_session.add(owner)
    await async_session.flush()
    project = Folder(name=f"project-{uuid4()}", user_id=owner.id)
    async_session.add(project)
    await async_session.flush()

    service = _AdminDeploymentAuthz(allowed_project_ids=set())
    _install_deployment_authz(monkeypatch, service)

    with pytest.raises(HTTPException) as exc_info:
        await resolve_project_id_for_deployment_create(
            session=async_session,
            current_user=actor,
            requested_project_id=project.id,
        )

    assert exc_info.value.status_code == 404
    assert str(project.id) not in str(exc_info.value.detail)
    assert len(service.calls) == 1


@pytest.mark.anyio
async def test_share_aware_lookup_loads_foreign_owned_flow_version(monkeypatch, async_session):
    """The real lookup query crosses owners only after the plugin opts in."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User

    actor = User(username=f"actor-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    owner = User(username=f"owner-{uuid4()}", password="not-a-secret", is_active=True)  # noqa: S106
    async_session.add(actor)
    async_session.add(owner)
    await async_session.flush()

    project = Folder(name=f"project-{uuid4()}", user_id=owner.id)
    async_session.add(project)
    await async_session.flush()
    flow = Flow(
        name="shared-flow",
        user_id=owner.id,
        folder_id=project.id,
        data={"nodes": [], "edges": []},
    )
    async_session.add(flow)
    await async_session.flush()
    version = FlowVersion(
        flow_id=flow.id,
        user_id=owner.id,
        version_number=1,
        data={"nodes": [], "edges": []},
    )
    async_session.add(version)
    await async_session.flush()

    service = _DeploymentPolicyAuthz(allowed_flow_ids={flow.id})
    _install_deployment_authz(monkeypatch, service)

    authorized = await authorize_flow_versions_for_deployment(
        session=async_session,
        current_user=actor,
        project_id=project.id,
        flow_version_ids=[version.id],
    )

    assert authorized == frozenset({version.id})
    assert service.calls[0]["obj"] == f"flow:{flow.id}"


@pytest.mark.anyio
async def test_admin_role_can_deploy_owned_and_user_shared_flows(monkeypatch, fake_user):
    """An admin policy must be evaluated for every owned or user-shared flow."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment

    project_id = uuid4()
    owned = _flow_version_row(project_id=project_id, owner_id=fake_user.id)
    shared = _flow_version_row(project_id=project_id)
    service = _DeploymentPolicyAuthz(allowed_flow_ids={owned.flow_id, shared.flow_id})
    _install_deployment_authz(monkeypatch, service)

    authorized = await authorize_flow_versions_for_deployment(
        session=_RowsSession([owned, shared]),
        current_user=fake_user,
        project_id=project_id,
        flow_version_ids=[owned.flow_version_id, shared.flow_version_id],
    )

    assert authorized == frozenset({owned.flow_version_id, shared.flow_version_id})
    assert [call["obj"] for call in service.calls] == [f"flow:{owned.flow_id}", f"flow:{shared.flow_id}"]


@pytest.mark.anyio
async def test_read_share_cannot_be_used_to_deploy(monkeypatch, fake_user):
    """A share that does not grant deploy fails with a UUID-private 404."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment

    project_id = uuid4()
    shared = _flow_version_row(project_id=project_id)
    service = _DeploymentPolicyAuthz(allowed_flow_ids=set())
    _install_deployment_authz(monkeypatch, service)

    with pytest.raises(HTTPException) as exc_info:
        await authorize_flow_versions_for_deployment(
            session=_RowsSession([shared]),
            current_user=fake_user,
            project_id=project_id,
            flow_version_ids=[shared.flow_version_id],
        )

    assert exc_info.value.status_code == 404
    assert str(shared.flow_version_id) not in str(exc_info.value.detail)


@pytest.mark.anyio
async def test_team_admin_share_can_deploy_shared_flow(monkeypatch, fake_user):
    """A plugin team grant reaches the same per-flow deploy boundary."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment

    project_id = uuid4()
    team_shared = _flow_version_row(project_id=project_id)
    service = _DeploymentPolicyAuthz(allowed_flow_ids={team_shared.flow_id})
    _install_deployment_authz(monkeypatch, service)

    authorized = await authorize_flow_versions_for_deployment(
        session=_RowsSession([team_shared]),
        current_user=fake_user,
        project_id=project_id,
        flow_version_ids=[team_shared.flow_version_id],
    )

    assert authorized == frozenset({team_shared.flow_version_id})
    assert service.calls[0]["act"] == "deploy"


@pytest.mark.anyio
async def test_mixed_flow_request_fails_closed_when_one_flow_is_denied(monkeypatch, fake_user):
    """A mixed allowed/denied request cannot partially reach the provider."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment

    project_id = uuid4()
    allowed = _flow_version_row(project_id=project_id)
    denied = _flow_version_row(project_id=project_id)
    service = _DeploymentPolicyAuthz(allowed_flow_ids={allowed.flow_id})
    _install_deployment_authz(monkeypatch, service)

    with pytest.raises(HTTPException) as exc_info:
        await authorize_flow_versions_for_deployment(
            session=_RowsSession([allowed, denied]),
            current_user=fake_user,
            project_id=project_id,
            flow_version_ids=[allowed.flow_version_id, denied.flow_version_id],
        )

    assert exc_info.value.status_code == 404
    assert [call["obj"] for call in service.calls] == [f"flow:{allowed.flow_id}", f"flow:{denied.flow_id}"]


@pytest.mark.anyio
async def test_missing_flow_version_returns_404_before_policy_enforcement(monkeypatch, fake_user):
    """Unknown and out-of-project UUIDs have the same non-disclosing response."""
    from langflow.services.authorization.deployment import authorize_flow_versions_for_deployment

    service = _DeploymentPolicyAuthz(allowed_flow_ids=set())
    _install_deployment_authz(monkeypatch, service)

    with pytest.raises(HTTPException) as exc_info:
        await authorize_flow_versions_for_deployment(
            session=_RowsSession([]),
            current_user=fake_user,
            project_id=uuid4(),
            flow_version_ids=[uuid4()],
        )

    assert exc_info.value.status_code == 404
    assert service.calls == []
