"""Tests for ensure_permission, ensure_flow_permission, audit_decision, filter_visible_resources."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization import utils as authz_utils
from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)


class _StubAuthorizationService:
    """Minimal stand-in for BaseAuthorizationService that records calls."""

    def __init__(self, *, allow: bool = True, batch_results: list[bool] | None = None) -> None:
        self.allow = allow
        self.batch_results = batch_results
        self.calls: list[dict] = []
        self.batch_calls: list[dict] = []

    async def enforce(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return self.allow

    async def batch_enforce(self, **kwargs) -> list[bool]:
        self.batch_calls.append(kwargs)
        if self.batch_results is not None:
            return self.batch_results
        return [self.allow] * len(kwargs.get("requests", []))


@pytest.fixture
def fake_user():
    """Build a non-superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=False)


@pytest.fixture
def fake_superuser():
    """Build a superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=True)


def _install_settings(monkeypatch, *, authz_enabled: bool, audit_enabled: bool = False) -> None:
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=authz_enabled,
            AUTHZ_AUDIT_ENABLED=audit_enabled,
        ),
    )
    monkeypatch.setattr(authz_utils, "get_settings_service", lambda: settings)


def _install_authz(monkeypatch, service: _StubAuthorizationService) -> None:
    monkeypatch.setattr(authz_utils, "get_authorization_service", lambda: service)


def _install_audit_recorder(monkeypatch) -> list[dict]:
    """Replace audit_decision with a recorder so tests can assert audit writes."""
    calls: list[dict] = []

    async def _recorder(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(authz_utils, "audit_decision", _recorder)
    return calls


# ----------------------------------------------------------------------------- #
# ensure_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_permission_noop_when_disabled(monkeypatch, fake_user):
    """When AUTHZ_ENABLED=False, the helper returns without consulting the service."""
    _install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_permission(fake_user, domain="*", obj="flow:abc", act="read")
    assert service.calls == []


@pytest.mark.anyio
async def test_ensure_permission_allows_when_enforce_returns_true(monkeypatch, fake_user):
    """A True enforce result returns None and forwards the merged context."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_permission(
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
async def test_ensure_permission_raises_403_when_denied(monkeypatch, fake_user):
    """A False enforce result raises HTTP 403 with a descriptive message."""
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    _install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await authz_utils.ensure_permission(fake_user, domain="*", obj="flow:abc", act="write")
    assert exc_info.value.status_code == 403
    assert "write" in exc_info.value.detail


@pytest.mark.anyio
async def test_ensure_permission_writes_audit_on_allow(monkeypatch, fake_user):
    """Allow path schedules an audit row with result='allow'."""
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=True))
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_permission(fake_user, domain="project:1", obj="flow:abc", act="read")

    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "allow"
    assert audit_calls[0]["obj"] == "flow:abc"
    assert audit_calls[0]["action"] == "flow:read"


@pytest.mark.anyio
async def test_ensure_permission_writes_audit_on_deny(monkeypatch, fake_user):
    """Deny path schedules an audit row with result='deny' before the 403 raises."""
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    audit_calls = _install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException):
        await authz_utils.ensure_permission(fake_user, domain="*", obj="flow:abc", act="delete")

    assert len(audit_calls) == 1
    assert audit_calls[0]["result"] == "deny"


# ----------------------------------------------------------------------------- #
# ensure_flow_permission — enum coercion, domain, owner override
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_flow_permission_accepts_enum(monkeypatch, fake_user):
    """A FlowAction enum is coerced to its string value before enforce."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    flow_id = uuid4()
    await authz_utils.ensure_flow_permission(fake_user, FlowAction.READ, flow_id=flow_id)

    assert service.calls[0]["act"] == "read"
    assert service.calls[0]["obj"] == f"flow:{flow_id}"


@pytest.mark.anyio
async def test_ensure_flow_permission_accepts_string_for_backcompat(monkeypatch, fake_user):
    """Bare string actions still work — gradual migration is allowed."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_flow_permission(fake_user, "write", flow_id=uuid4())
    assert service.calls[0]["act"] == "write"


@pytest.mark.anyio
async def test_ensure_flow_permission_computes_workspace_domain(monkeypatch, fake_user):
    """workspace_id is mapped to a workspace: domain string and forwarded in context."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    await authz_utils.ensure_flow_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    folder_id = uuid4()
    await authz_utils.ensure_flow_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    folder_id = uuid4()
    await authz_utils.ensure_flow_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_flow_permission(fake_user, FlowAction.CREATE)
    assert service.calls[0]["domain"] == "*"


def test_resolve_casbin_domain_precedence():
    """Domain precedence: project > workspace > '*'."""
    ws, scope = uuid4(), uuid4()
    assert authz_utils._resolve_casbin_domain(workspace_id=ws, scope_id=scope) == f"project:{scope}"
    assert authz_utils._resolve_casbin_domain(workspace_id=ws, scope_id=None) == f"workspace:{ws}"
    assert authz_utils._resolve_casbin_domain(workspace_id=None, scope_id=scope) == f"project:{scope}"
    assert authz_utils._resolve_casbin_domain(workspace_id=None, scope_id=None) == "*"
    # Backward-compatible alias still resolves to the same function.
    assert authz_utils._resolve_flow_domain is authz_utils._resolve_casbin_domain


@pytest.mark.anyio
async def test_owner_override_skips_enforce(monkeypatch, fake_user):
    """A flow owner short-circuits the enforce call entirely."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)  # Would deny if asked.
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_flow_permission(
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
    flipping ``AUTHZ_ENABLED``. ``_install_settings`` defaults the audit flag
    to False so we explicitly enable it here.
    """
    _install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_flow_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))
    _install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException):
        await authz_utils.ensure_flow_permission(
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
    """A ProjectAction enum is coerced to its string value before enforce."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    project_id = uuid4()
    await authz_utils.ensure_project_permission(fake_user, ProjectAction.READ, project_id=project_id)
    assert service.calls[0]["act"] == "read"
    assert service.calls[0]["obj"] == f"project:{project_id}"


@pytest.mark.anyio
async def test_ensure_project_permission_uses_workspace_domain(monkeypatch, fake_user):
    """workspace_id is mapped to a workspace: domain string and forwarded in context."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    workspace_id = uuid4()
    await authz_utils.ensure_project_permission(
        fake_user, ProjectAction.WRITE, project_id=uuid4(), project_user_id=uuid4(), workspace_id=workspace_id
    )
    assert service.calls[0]["domain"] == f"workspace:{workspace_id}"
    assert service.calls[0]["context"]["workspace_id"] == workspace_id


@pytest.mark.anyio
async def test_project_owner_override_skips_enforce(monkeypatch, fake_user):
    """A project owner short-circuits the enforce call entirely."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)  # Would deny if asked.
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_project_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_project_permission(fake_user, ProjectAction.CREATE)
    assert service.calls[0]["obj"] == "project:*"
    assert service.calls[0]["act"] == "create"


# ----------------------------------------------------------------------------- #
# audit_decision
# ----------------------------------------------------------------------------- #


def test_split_obj_parses_uuid_suffix():
    """flow:<uuid> splits into ('flow', UUID)."""
    flow_id = uuid4()
    resource_type, resource_id = authz_utils._split_obj(f"flow:{flow_id}")
    assert resource_type == "flow"
    assert resource_id == flow_id


def test_split_obj_wildcard_returns_none_id():
    """flow:* keeps resource_type but emits None for resource_id."""
    resource_type, resource_id = authz_utils._split_obj("flow:*")
    assert resource_type == "flow"
    assert resource_id is None


def test_split_obj_malformed_returns_nones():
    """A key without a colon returns (None, None)."""
    assert authz_utils._split_obj("nothing") == (None, None)


def test_split_obj_non_uuid_suffix_returns_none_id():
    """A non-UUID suffix is treated as a wildcard for the resource_id field."""
    resource_type, resource_id = authz_utils._split_obj("flow:not-a-uuid")
    assert resource_type == "flow"
    assert resource_id is None


@pytest.mark.anyio
async def test_audit_decision_runs_when_authz_disabled_but_audit_on(monkeypatch):
    """Audit is independent of enforcement now.

    Previously ``audit_decision`` short-circuited when ``AUTHZ_ENABLED=False``,
    which meant share CRUD writes left no audit trail on default installs. The
    new contract gates only on ``AUTHZ_AUDIT_ENABLED`` so operators can
    observe traffic before flipping enforcement on.
    """
    _install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)
    scheduled: list[object] = []

    class _FakeTask:
        def add_done_callback(self, cb):
            self._cb = cb

        def done(self) -> bool:
            return False

    def _capture(coro):
        coro.close()
        task = _FakeTask()
        scheduled.append(task)
        return task

    monkeypatch.setattr("asyncio.create_task", _capture)

    await authz_utils.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")
    try:
        assert len(scheduled) == 1
    finally:
        # Don't pollute the module-global pending set for downstream tests.
        for task in scheduled:
            authz_utils._pending_audit_tasks.discard(task)


@pytest.mark.anyio
async def test_audit_decision_noop_when_audit_disabled(monkeypatch):
    """AUTHZ_AUDIT_ENABLED=False suppresses audit writes."""
    _install_settings(monkeypatch, authz_enabled=True, audit_enabled=False)
    scheduled: list[object] = []
    monkeypatch.setattr("asyncio.create_task", lambda coro: scheduled.append(coro) or coro)

    await authz_utils.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")
    assert scheduled == []


@pytest.mark.anyio
async def test_audit_decision_schedules_task_when_enabled(monkeypatch):
    """A scheduled coroutine is produced when both flags are on.

    The new implementation tracks the task in ``_pending_audit_tasks`` so the
    event loop cannot GC it mid-write and so shutdown can drain it. Our mock
    returns a lightweight stand-in that supports ``add_done_callback`` exactly
    as a real ``asyncio.Task`` does.
    """
    _install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)
    scheduled: list[object] = []

    class _FakeTask:
        def __init__(self, coro):
            self._coro = coro
            self._callbacks: list = []

        def add_done_callback(self, cb):
            self._callbacks.append(cb)

        def done(self) -> bool:
            return False

    def _capture(coro):
        coro.close()  # don't actually run — the function imports from DB modules.
        task = _FakeTask(coro)
        scheduled.append(task)
        return task

    monkeypatch.setattr("asyncio.create_task", _capture)

    await authz_utils.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")
    try:
        assert len(scheduled) == 1
        # The implementation must hold a reference so the GC can't drop the task.
        assert scheduled[0] in authz_utils._pending_audit_tasks
        # And it must register a done-callback that removes itself from the set.
        assert scheduled[0]._callbacks, "audit_decision must register a done-callback to clean up _pending_audit_tasks"
    finally:
        # The fake task is not a real ``asyncio.Task`` — clean up the
        # module-global set so the next test starts from an empty state.
        authz_utils._pending_audit_tasks.discard(scheduled[0])


@pytest.mark.anyio
async def test_drain_pending_audit_writes_awaits_tasks():
    """drain_pending_audit_writes waits for tracked tasks to finish."""
    import asyncio

    finished = asyncio.Event()

    async def _slow() -> None:
        await asyncio.sleep(0.01)
        finished.set()

    task = asyncio.create_task(_slow())
    authz_utils._pending_audit_tasks.add(task)
    task.add_done_callback(authz_utils._pending_audit_tasks.discard)

    await authz_utils.drain_pending_audit_writes(timeout=1.0)
    assert finished.is_set()
    assert task not in authz_utils._pending_audit_tasks


@pytest.mark.anyio
async def test_ensure_permission_fails_closed_on_plugin_exception(monkeypatch, fake_user):
    """If the authz plugin raises, ensure_permission must deny (403), not bubble 500."""
    _install_settings(monkeypatch, authz_enabled=True, audit_enabled=False)

    class _BrokenPlugin:
        async def enforce(self, **_kwargs):
            msg = "policy store down"
            raise RuntimeError(msg)

        async def batch_enforce(self, **_kwargs):
            return []

    monkeypatch.setattr(authz_utils, "get_authorization_service", lambda: _BrokenPlugin())
    captured = _install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        await authz_utils.ensure_permission(fake_user, domain="*", obj="flow:abc", act="read")

    assert excinfo.value.status_code == 403, "Plugin exceptions must fail closed (deny), not 500"
    # The deny path must still emit an audit row so the operator can see the failure.
    assert captured, "Plugin exception must still produce an audit row"
    assert captured[0]["result"] == "deny"
    assert "error" in captured[0]["details"]


# ----------------------------------------------------------------------------- #
# filter_visible_resources
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_filter_visible_resources_noop_when_disabled(monkeypatch, fake_user):
    """No batch_enforce call when AUTHZ_ENABLED=False; returns input unchanged."""
    _install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)

    candidates = [SimpleNamespace(id=uuid4()) for _ in range(3)]
    result = await authz_utils.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=candidates,
    )
    assert result == candidates
    assert service.batch_calls == []


@pytest.mark.anyio
async def test_filter_visible_resources_empty_returns_empty(monkeypatch, fake_user):
    """An empty candidates list is returned unchanged without contacting the service."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)

    result = await authz_utils.filter_visible_resources(fake_user, resource_type="flow", candidates=[])
    assert result == []
    assert service.batch_calls == []


@pytest.mark.anyio
async def test_filter_visible_resources_filters_via_batch_enforce(monkeypatch, fake_user):
    """When AUTHZ_ENABLED=True, batch_enforce results filter the candidate list."""
    _install_settings(monkeypatch, authz_enabled=True)
    candidates = [SimpleNamespace(id=uuid4()) for _ in range(3)]
    service = _StubAuthorizationService(batch_results=[True, False, True])
    _install_authz(monkeypatch, service)

    result = await authz_utils.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=candidates,
    )

    assert result == [candidates[0], candidates[2]]
    assert service.batch_calls[0]["requests"] == [
        (f"flow:{candidates[0].id}", "read"),
        (f"flow:{candidates[1].id}", "read"),
        (f"flow:{candidates[2].id}", "read"),
    ]


@pytest.mark.anyio
async def test_filter_visible_resources_accepts_custom_key(monkeypatch, fake_user):
    """A custom key extractor lets callers filter non-id-bearing items."""
    _install_settings(monkeypatch, authz_enabled=True)
    items = [{"resource_id": uuid4()}, {"resource_id": uuid4()}]
    service = _StubAuthorizationService(batch_results=[False, True])
    _install_authz(monkeypatch, service)

    result = await authz_utils.filter_visible_resources(
        fake_user,
        resource_type="project",
        candidates=items,
        key=lambda r: r["resource_id"],
        act=FlowAction.WRITE,
    )

    assert result == [items[1]]
    assert service.batch_calls[0]["requests"][0][1] == "write"


@pytest.mark.anyio
async def test_filter_visible_resources_groups_by_extracted_domain(monkeypatch, fake_user):
    """With ``domain_extractor`` set, batch_enforce is called once per unique domain.

    Each call sees only the candidates that resolved to that domain, so the
    authorization plugin evaluates each candidate against the right policy tuple
    (the single-domain default would force every candidate through the same
    wildcard domain, hiding project-scoped grants).
    """
    _install_settings(monkeypatch, authz_enabled=True)
    workspace_a = uuid4()
    workspace_b = uuid4()

    items = [
        SimpleNamespace(id=uuid4(), workspace_id=workspace_a, folder_id=None),
        SimpleNamespace(id=uuid4(), workspace_id=workspace_b, folder_id=None),
        SimpleNamespace(id=uuid4(), workspace_id=workspace_a, folder_id=None),
    ]

    # Deny everything in workspace_b, allow everything in workspace_a.
    class _DomainAwareStub:
        def __init__(self) -> None:
            self.batch_calls: list[dict] = []

        async def batch_enforce(self, **kwargs) -> list[bool]:
            self.batch_calls.append(kwargs)
            allowed = kwargs["domain"] != f"workspace:{workspace_b}"
            return [allowed] * len(kwargs["requests"])

    service = _DomainAwareStub()
    _install_authz(monkeypatch, service)

    result = await authz_utils.filter_visible_resources(
        fake_user,
        resource_type="project",
        candidates=items,
        domain_extractor=lambda project: authz_utils._resolve_casbin_domain(project.workspace_id, None),
        act=FlowAction.READ,
    )

    # Two calls — one per unique domain.
    domains_called = {call["domain"] for call in service.batch_calls}
    assert domains_called == {f"workspace:{workspace_a}", f"workspace:{workspace_b}"}

    # Output preserves the original order, with workspace_b's item dropped.
    assert result == [items[0], items[2]]


@pytest.mark.anyio
async def test_filter_visible_resources_owner_override_skips_enforcer(monkeypatch, fake_user):
    """Items owned by the caller are force-included without consulting the enforcer.

    Mirrors the owner-override short-circuit in ``_ensure_resource_permission``
    so list and direct-read agree under plugin enforcement. Without this,
    a deny-all plugin would hide the caller's own rows from the listing
    response while letting them read the same rows directly.
    """
    _install_settings(monkeypatch, authz_enabled=True)
    other_user = uuid4()

    items = [
        SimpleNamespace(id=uuid4(), user_id=fake_user.id),  # owned → must keep
        SimpleNamespace(id=uuid4(), user_id=other_user),  # not owned → enforcer decides
        SimpleNamespace(id=uuid4(), user_id=fake_user.id),  # owned → must keep
    ]
    # Deny-all stub so any item that reaches the enforcer would be dropped.
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)

    result = await authz_utils.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=items,
        owner_extractor=lambda item: item.user_id,
        act=FlowAction.READ,
    )

    # Owned items kept (positions 0 and 2); non-owned item dropped by deny.
    assert result == [items[0], items[2]]
    # Enforcer was consulted only for the non-owned item.
    assert len(service.batch_calls) == 1
    assert len(service.batch_calls[0]["requests"]) == 1


# ----------------------------------------------------------------------------- #
# ensure_deployment_permission
# ----------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_ensure_deployment_permission_uses_project_domain(monkeypatch, fake_user):
    """project_id maps to project: domain (same helper as flows' folder_id)."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    project_id = uuid4()
    await authz_utils.ensure_deployment_permission(
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
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_deployment_permission(
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


# --------------------------------------------------------------------------- #
# ensure_knowledge_base_permission
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_kb_permission_uses_kb_id_object_slug(monkeypatch, fake_user):
    """KB shares store UUIDs; the policy object slug must use ``kb_id``."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    kb_id = uuid4()
    await authz_utils.ensure_knowledge_base_permission(
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
    """KB owner is allowed even when the enforcer denies."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_knowledge_base_permission(
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
    """Non-owner + denied enforcer → 403 from the helper."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await authz_utils.ensure_knowledge_base_permission(
            fake_user,
            KnowledgeBaseAction.DELETE,
            kb_id=uuid4(),
            kb_name="someone-elses",
            kb_user_id=uuid4(),
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_kb_permission_create_uses_wildcard_slug(monkeypatch, fake_user):
    """Without a kb_id (create flow) the slug is ``knowledge_base:*``."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_knowledge_base_permission(
        fake_user,
        KnowledgeBaseAction.CREATE,
        kb_user_id=fake_user.id,
    )

    # Owner-override fires; no enforce call. The audit row gets the wildcard
    # slug so the dry-run CLI / audit query view shows it consistently.
    assert service.calls == []


# --------------------------------------------------------------------------- #
# ensure_variable_permission
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_variable_permission_uses_variable_object_slug(monkeypatch, fake_user):
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    variable_id = uuid4()
    await authz_utils.ensure_variable_permission(
        fake_user,
        VariableAction.WRITE,
        variable_id=variable_id,
        variable_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"variable:{variable_id}"


@pytest.mark.anyio
async def test_variable_permission_owner_override(monkeypatch, fake_user):
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_variable_permission(
        fake_user,
        VariableAction.DELETE,
        variable_id=uuid4(),
        variable_user_id=fake_user.id,
    )

    assert service.calls == []
    assert audit_calls[0]["result"] == "owner_override"


# --------------------------------------------------------------------------- #
# ensure_file_permission
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_file_permission_uses_file_object_slug(monkeypatch, fake_user):
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    file_id = uuid4()
    await authz_utils.ensure_file_permission(
        fake_user,
        FileAction.READ,
        file_id=file_id,
        file_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"file:{file_id}"


@pytest.mark.anyio
async def test_file_permission_owner_override(monkeypatch, fake_user):
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)
    audit_calls = _install_audit_recorder(monkeypatch)

    await authz_utils.ensure_file_permission(
        fake_user,
        FileAction.DELETE,
        file_id=uuid4(),
        file_user_id=fake_user.id,
    )

    assert service.calls == []
    assert audit_calls[0]["result"] == "owner_override"


# --------------------------------------------------------------------------- #
# ensure_share_permission
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_share_permission_uses_share_object_slug(monkeypatch, fake_user):
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)
    _install_audit_recorder(monkeypatch)

    share_id = uuid4()
    await authz_utils.ensure_share_permission(
        fake_user,
        ShareAction.CREATE,
        share_id=share_id,
        share_user_id=uuid4(),
    )

    assert service.calls[0]["obj"] == f"share:{share_id}"
    assert service.calls[0]["act"] == "create"
