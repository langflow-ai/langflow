"""Tests for ``ensure_permission`` and the ``ensure_*_permission`` family."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization import guards as authz_guards
from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)

from ._common import (
    _StubAuthorizationService,
    install_audit_recorder,
    install_authz,
    install_settings,
)

# ----------------------------------------------------------------------------- #
# ensure_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_permission_noop_when_disabled(monkeypatch, fake_user):
    """When AUTHZ_ENABLED=False, the helper returns without consulting the service."""
    install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_permission(fake_user, domain="*", obj="flow:abc", act="read")
    assert service.calls == []


@pytest.mark.anyio
async def test_ensure_permission_allows_when_enforce_returns_true(monkeypatch, fake_user):
    """A True enforce result returns None and forwards the merged context."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_permission(
        fake_user,
        domain="*",
        obj="flow:abc",
        act="read",
        context={"extra": "value"},
    )

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["user_id"] == fake_user.id
    assert call["obj"] == "flow:abc"
    assert call["act"] == "read"
    assert call["context"] == {"is_superuser": False, "extra": "value"}


@pytest.mark.anyio
async def test_ensure_permission_caller_context_cannot_override_is_superuser(monkeypatch, fake_user):
    """Caller-supplied context must not be able to overwrite the user-derived is_superuser flag.

    Regression for PR #13153 review: previously the merge was
    ``{**_auth_context(user), **(context or {})}`` which let a caller forge
    ``context={"is_superuser": True}`` for a non-superuser. The merged context
    forwarded to ``enforce`` must always reflect the user's actual privilege.
    """
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_permission(
        fake_user,
        domain="*",
        obj="flow:abc",
        act="read",
        context={"is_superuser": True, "extra": "value"},
    )

    assert len(service.calls) == 1
    forwarded_context = service.calls[0]["context"]
    assert forwarded_context["is_superuser"] is False
    assert forwarded_context["extra"] == "value"


@pytest.mark.anyio
async def test_ensure_permission_raises_403_with_non_disclosing_default(monkeypatch, fake_user):
    """Default deny detail must NOT echo the resource UUID — see PR #13153 review item I2."""
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    install_audit_recorder(monkeypatch)

    flow_id = uuid4()
    with pytest.raises(HTTPException) as exc_info:
        await authz_guards.ensure_permission(fake_user, domain="*", obj=f"flow:{flow_id}", act="write")

    assert exc_info.value.status_code == 403
    # The default message MUST NOT contain the resource UUID or the action verb —
    # otherwise a caller that forgets to wrap in deny_to_404 leaks existence.
    detail = exc_info.value.detail.lower()
    assert str(flow_id) not in detail
    assert "write" not in detail
    assert "permission denied" in detail


@pytest.mark.anyio
async def test_ensure_permission_accepts_explicit_detail_override(monkeypatch, fake_user):
    """Callers that have already verified resource existence may pass a richer message."""
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await authz_guards.ensure_permission(
            fake_user,
            domain="*",
            obj="flow:abc",
            act="write",
            detail="Cannot edit a published flow.",
        )

    assert exc_info.value.detail == "Cannot edit a published flow."


@pytest.mark.anyio
async def test_ensure_permission_writes_audit_on_allow(monkeypatch, fake_user):
    """Allow path schedules an audit row with result='allow'."""
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=True))
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_permission(fake_user, domain="project:1", obj="flow:abc", act="read")

    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "allow"
    assert audit_calls[0]["obj"] == "flow:abc"
    assert audit_calls[0]["action"] == "flow:read"


@pytest.mark.anyio
async def test_ensure_permission_writes_audit_on_deny(monkeypatch, fake_user):
    """Deny path schedules an audit row with result='deny' before the 403 raises."""
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    audit_calls = install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException):
        await authz_guards.ensure_permission(fake_user, domain="*", obj="flow:abc", act="delete")

    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "deny"


# ----------------------------------------------------------------------------- #
# ensure_flow_permission — enum coercion, domain, owner override
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_flow_permission_accepts_enum(monkeypatch, fake_user):
    """A FlowAction enum is coerced to its string value before enforce."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    flow_id = uuid4()
    await authz_guards.ensure_flow_permission(fake_user, FlowAction.READ, flow_id=flow_id)

    assert service.calls[0]["act"] == "read"
    assert service.calls[0]["obj"] == f"flow:{flow_id}"


@pytest.mark.anyio
async def test_ensure_flow_permission_accepts_string_for_backcompat(monkeypatch, fake_user):
    """Bare string actions still work — gradual migration is allowed."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_flow_permission(fake_user, "write", flow_id=uuid4())
    assert service.calls[0]["act"] == "write"


@pytest.mark.anyio
async def test_ensure_flow_permission_computes_workspace_domain(monkeypatch, fake_user):
    """workspace_id is mapped to a workspace: domain string and forwarded in context."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    await authz_guards.ensure_flow_permission(
        fake_user,
        FlowAction.READ,
        flow_id=uuid4(),
        flow_user_id=uuid4(),
        workspace_id=workspace_id,
    )

    assert service.calls[0]["domain"] == f"workspace:{workspace_id}"
    assert service.calls[0]["context"]["workspace_id"] == workspace_id


@pytest.mark.anyio
async def test_ensure_flow_permission_falls_back_to_project_domain(monkeypatch, fake_user):
    """Without workspace_id, folder_id maps to a project: domain string."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    folder_id = uuid4()
    await authz_guards.ensure_flow_permission(
        fake_user,
        FlowAction.READ,
        flow_id=uuid4(),
        flow_user_id=uuid4(),
        folder_id=folder_id,
    )

    assert service.calls[0]["domain"] == f"project:{folder_id}"
    assert service.calls[0]["context"]["folder_id"] == folder_id
    assert service.calls[0]["context"]["workspace_id"] is None


@pytest.mark.anyio
async def test_ensure_flow_permission_project_beats_workspace(monkeypatch, fake_user):
    """Project domain wins when both workspace_id and folder_id are set."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    folder_id = uuid4()
    await authz_guards.ensure_flow_permission(
        fake_user,
        FlowAction.READ,
        flow_id=uuid4(),
        flow_user_id=uuid4(),
        workspace_id=workspace_id,
        folder_id=folder_id,
    )

    assert service.calls[0]["domain"] == f"project:{folder_id}"
    # workspace_id is still passed in context so the plugin can use it for ABAC matchers.
    assert service.calls[0]["context"]["folder_id"] == folder_id
    assert service.calls[0]["context"]["workspace_id"] == workspace_id


@pytest.mark.anyio
async def test_ensure_flow_permission_wildcard_domain_when_neither_set(monkeypatch, fake_user):
    """With neither workspace_id nor folder_id, domain falls back to '*'."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_flow_permission(fake_user, FlowAction.CREATE)
    assert service.calls[0]["domain"] == "*"


@pytest.mark.anyio
async def test_owner_override_skips_enforce(monkeypatch, fake_user):
    """A flow owner short-circuits the enforce call entirely."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)  # Would deny if asked.
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_flow_permission(
        fake_user,
        FlowAction.DELETE,
        flow_id=uuid4(),
        flow_user_id=fake_user.id,
        workspace_id=uuid4(),
    )

    assert service.calls == []
    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "owner_override"


@pytest.mark.anyio
async def test_owner_override_audits_even_when_authz_disabled(monkeypatch, fake_user):
    """Owner override on a disabled-authz install still writes an audit row.

    Audit is now gated only on ``AUTHZ_AUDIT_ENABLED`` (the audit recorder
    here intercepts at that level), so operators can observe traffic ahead of
    flipping ``AUTHZ_ENABLED``. ``install_settings`` defaults the audit flag
    to False so we explicitly enable it here.
    """
    install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_flow_permission(
        fake_user,
        FlowAction.WRITE,
        flow_id=uuid4(),
        flow_user_id=fake_user.id,
    )
    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "owner_override"


@pytest.mark.anyio
async def test_non_owner_falls_through_to_enforce(monkeypatch, fake_user):
    """When flow_user_id differs from current user, enforce is called normally."""
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException):
        await authz_guards.ensure_flow_permission(
            fake_user,
            FlowAction.WRITE,
            flow_id=uuid4(),
            flow_user_id=uuid4(),
        )


# ----------------------------------------------------------------------------- #
# ensure_project_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_project_permission_accepts_enum(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    project_id = uuid4()
    await authz_guards.ensure_project_permission(fake_user, ProjectAction.READ, project_id=project_id)
    assert service.calls[0]["act"] == "read"
    assert service.calls[0]["obj"] == f"project:{project_id}"


@pytest.mark.anyio
async def test_ensure_project_permission_uses_workspace_domain(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    await authz_guards.ensure_project_permission(
        fake_user, ProjectAction.WRITE, project_id=uuid4(), project_user_id=uuid4(), workspace_id=workspace_id
    )
    assert service.calls[0]["domain"] == f"workspace:{workspace_id}"
    assert service.calls[0]["context"]["workspace_id"] == workspace_id


@pytest.mark.anyio
async def test_project_owner_override_skips_enforce(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_project_permission(
        fake_user,
        ProjectAction.DELETE,
        project_id=uuid4(),
        project_user_id=fake_user.id,
        workspace_id=uuid4(),
    )

    assert service.calls == []
    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "owner_override"


@pytest.mark.anyio
async def test_ensure_project_permission_create_uses_wildcard_obj(monkeypatch, fake_user):
    """ProjectAction.CREATE without a project_id targets ``project:*`` (workspace-scoped create)."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_project_permission(fake_user, ProjectAction.CREATE)
    assert service.calls[0]["obj"] == "project:*"
    assert service.calls[0]["act"] == "create"


# ----------------------------------------------------------------------------- #
# ensure_deployment_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_deployment_permission_uses_project_domain(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    project_id = uuid4()
    await authz_guards.ensure_deployment_permission(
        fake_user,
        DeploymentAction.READ,
        deployment_id=uuid4(),
        deployment_user_id=uuid4(),
        project_id=project_id,
    )

    assert service.calls[0]["domain"] == f"project:{project_id}"
    assert service.calls[0]["context"]["project_id"] == project_id


@pytest.mark.anyio
async def test_deployment_owner_override_skips_enforce(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_deployment_permission(
        fake_user,
        DeploymentAction.DELETE,
        deployment_id=uuid4(),
        deployment_user_id=fake_user.id,
        project_id=uuid4(),
    )

    assert service.calls == []
    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "owner_override"
    assert audit_calls[0]["action"] == "deployment:delete"


# ----------------------------------------------------------------------------- #
# ensure_knowledge_base_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_kb_permission_uses_kb_id_object_slug(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    kb_id = uuid4()
    await authz_guards.ensure_knowledge_base_permission(
        fake_user,
        KnowledgeBaseAction.READ,
        kb_id=kb_id,
        kb_name="my-kb",
        kb_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"knowledge_base:{kb_id}"
    assert service.calls[0]["act"] == "read"
    # ``kb_name`` is forwarded in the context for debugging.
    assert service.calls[0]["context"]["kb_name"] == "my-kb"
    assert service.calls[0]["context"]["kb_id"] == kb_id


@pytest.mark.anyio
async def test_kb_permission_owner_override(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_knowledge_base_permission(
        fake_user,
        KnowledgeBaseAction.DELETE,
        kb_id=uuid4(),
        kb_name="my-kb",
        kb_user_id=fake_user.id,
    )

    assert service.calls == []
    assert audit_calls[0]["result"] == "owner_override"
    assert audit_calls[0]["action"] == "knowledge_base:delete"


@pytest.mark.anyio
async def test_kb_permission_denied_raises_403(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await authz_guards.ensure_knowledge_base_permission(
            fake_user,
            KnowledgeBaseAction.DELETE,
            kb_id=uuid4(),
            kb_name="someone-elses",
            kb_user_id=uuid4(),
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_kb_permission_create_uses_wildcard_slug(monkeypatch, fake_user):
    """Without a kb_id (create flow) the owner override fires; no enforce call."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    await authz_guards.ensure_knowledge_base_permission(
        fake_user,
        KnowledgeBaseAction.CREATE,
        kb_user_id=fake_user.id,
    )

    assert service.calls == []


# ----------------------------------------------------------------------------- #
# ensure_variable_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_variable_permission_uses_variable_object_slug(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    variable_id = uuid4()
    await authz_guards.ensure_variable_permission(
        fake_user,
        VariableAction.WRITE,
        variable_id=variable_id,
        variable_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"variable:{variable_id}"


@pytest.mark.anyio
async def test_variable_permission_owner_override(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_variable_permission(
        fake_user,
        VariableAction.DELETE,
        variable_id=uuid4(),
        variable_user_id=fake_user.id,
    )

    assert service.calls == []
    assert audit_calls[0]["result"] == "owner_override"


# ----------------------------------------------------------------------------- #
# ensure_file_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_file_permission_uses_file_object_slug(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    file_id = uuid4()
    await authz_guards.ensure_file_permission(
        fake_user,
        FileAction.READ,
        file_id=file_id,
        file_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"file:{file_id}"


@pytest.mark.anyio
async def test_file_permission_owner_override(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)
    audit_calls = install_audit_recorder(monkeypatch)

    await authz_guards.ensure_file_permission(
        fake_user,
        FileAction.DELETE,
        file_id=uuid4(),
        file_user_id=fake_user.id,
    )

    assert service.calls == []
    assert audit_calls[0]["result"] == "owner_override"


# ----------------------------------------------------------------------------- #
# ensure_share_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_share_permission_uses_share_object_slug(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)

    share_id = uuid4()
    await authz_guards.ensure_share_permission(
        fake_user,
        ShareAction.CREATE,
        share_id=share_id,
        share_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"share:{share_id}"
    assert service.calls[0]["act"] == "create"
