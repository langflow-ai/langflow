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
