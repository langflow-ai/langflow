"""Unit cover for the LE-1905 authorization-report fixes that live in OSS."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from langflow.services.authorization import audit as audit_module
from langflow.services.authorization.fetch import deny_to_404, deny_to_404_unless_readable

# --------------------------------------------------------------------------- #
# Finding 1: a permission check must not read as a performed action.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_guard_decisions_are_tagged_as_decisions(monkeypatch):
    """Every row a guard writes carries the decision marker."""
    from langflow.services.authorization import guards

    captured: list[dict] = []

    async def _capture(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(audit_module, "audit_decision", _capture)

    await guards._audit_guard_decision(
        user_id=uuid4(),
        action="share:create",
        obj="share:*",
        result=audit_module.AUDIT_OWNER_OVERRIDE,
        details={"domain": "*"},
    )

    assert captured[0]["details"]["event"] == audit_module.AUDIT_EVENT_DECISION
    # The caller's own details survive alongside the marker.
    assert captured[0]["details"]["domain"] == "*"


def test_decision_and_mutation_markers_are_distinct():
    assert audit_module.AUDIT_EVENT_DECISION != audit_module.AUDIT_EVENT_MUTATION


# --------------------------------------------------------------------------- #
# Finding 8: a denial on a resource the caller can read is a 403, not a 404.
# --------------------------------------------------------------------------- #


def _denied() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@pytest.mark.asyncio
async def test_readable_resource_keeps_the_403():
    async def _can_read() -> None:
        return None

    resolved = await deny_to_404_unless_readable(
        _denied(), _can_read, denied_detail="You don't have permission to execute this flow."
    )

    assert resolved.status_code == status.HTTP_403_FORBIDDEN
    assert resolved.detail == "You don't have permission to execute this flow."


@pytest.mark.asyncio
async def test_unreadable_resource_still_masks_as_404():
    async def _cannot_read() -> None:
        raise _denied()

    resolved = await deny_to_404_unless_readable(
        _denied(), _cannot_read, denied_detail="never used", not_found_detail="Flow not found"
    )

    assert resolved.status_code == status.HTTP_404_NOT_FOUND
    assert resolved.detail == "Flow not found"


@pytest.mark.asyncio
async def test_service_failure_during_the_read_check_is_not_a_404():
    """A 503 from the plugin means "cannot decide", not "does not exist".

    Collapsing it to 404 would hide an authorization-service outage behind a
    routine-looking response and send the caller to check an id that is fine.
    """
    unavailable = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="authz plugin down")

    async def _read_check_fails() -> None:
        raise unavailable

    resolved = await deny_to_404_unless_readable(
        _denied(), _read_check_fails, denied_detail="never used", not_found_detail="Flow not found"
    )

    assert resolved is unavailable
    assert resolved.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_non_403_is_surfaced_unchanged():
    """A 503 from the plugin must never be relabelled as a permission answer."""
    upstream = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="plugin down")

    async def _unreachable() -> None:  # pragma: no cover - must not be called
        pytest.fail("read check ran for a non-403")

    resolved = await deny_to_404_unless_readable(upstream, _unreachable, denied_detail="x")

    assert resolved is upstream
    assert deny_to_404(upstream).status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# --------------------------------------------------------------------------- #
# Finding 11: owner override covers creating a flow in a project you own.
# --------------------------------------------------------------------------- #


def test_flow_spec_inherits_ownership_from_the_destination_project():
    from langflow.services.authorization.guards import _RESOURCE_SPECS

    assert _RESOURCE_SPECS["flow"].create_container_owner_kw == "folder_user_id"
    # The flow's own owner kwarg still must not enable the override on create:
    # it is the caller-supplied field and would let anyone assert ownership.
    assert _RESOURCE_SPECS["flow"].owner_override_on_create is False


@pytest.mark.asyncio
async def test_create_in_owned_project_takes_the_owner_override(monkeypatch):
    """The plugin is never consulted: ownership is checked before any policy rule."""
    from langflow.services.authorization import guards

    user_id = uuid4()
    project_id = uuid4()
    results: list[str] = []

    async def _capture(**kwargs):
        results.append(kwargs["result"])

    async def _never(*_args, **_kwargs) -> None:  # pragma: no cover - must not be called
        pytest.fail("enforce() ran despite owner override")

    monkeypatch.setattr(audit_module, "audit_decision", _capture)
    monkeypatch.setattr(guards, "ensure_permission", _never)
    monkeypatch.setattr(guards, "should_apply_owner_override", lambda: _true())

    class _User:
        id = user_id

    await guards.ensure_flow_permission(
        _User(), "create", workspace_id=None, folder_id=project_id, folder_user_id=user_id
    )

    assert results == [audit_module.AUDIT_OWNER_OVERRIDE]


@pytest.mark.asyncio
async def test_create_in_someone_elses_project_still_reaches_the_policy(monkeypatch):
    from langflow.services.authorization import guards

    reached: list[str] = []

    async def _record(_user, **kwargs):
        reached.append(kwargs["act"])

    monkeypatch.setattr(guards, "ensure_permission", _record)

    class _User:
        id = uuid4()

    await guards.ensure_flow_permission(_User(), "create", workspace_id=None, folder_id=uuid4(), folder_user_id=uuid4())

    assert reached == ["create"]


async def _true() -> bool:
    return True


# --------------------------------------------------------------------------- #
# Round 2, finding 1: a capability probe is not an action, so it is not audited.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_capability_probe_writes_no_decision_row(monkeypatch):
    """The UI asking whether to offer a control must not log ``share:create``."""
    from langflow.services.authorization import capability_probe, guards

    captured: list[dict] = []

    async def _capture(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(audit_module, "audit_decision", _capture)

    with capability_probe():
        await guards._audit_guard_decision(
            user_id=uuid4(),
            action="share:create",
            obj="share:*",
            result=audit_module.AUDIT_OWNER_OVERRIDE,
        )

    assert captured == []


@pytest.mark.asyncio
async def test_probe_suppression_does_not_leak_past_the_scope(monkeypatch):
    """A real attempt after a probe is audited as usual."""
    from langflow.services.authorization import capability_probe, guards

    captured: list[dict] = []

    async def _capture(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(audit_module, "audit_decision", _capture)

    with capability_probe():
        await guards._audit_guard_decision(
            user_id=uuid4(),
            action="share:create",
            obj="share:*",
            result=audit_module.AUDIT_ALLOW,
        )
    await guards._audit_guard_decision(
        user_id=uuid4(),
        action="share:create",
        obj="share:abc",
        result=audit_module.AUDIT_DENY,
    )

    assert len(captured) == 1
    assert captured[0]["result"] == audit_module.AUDIT_DENY


# --------------------------------------------------------------------------- #
# Round 2, finding 3: the Playground posts the canvas, so a non-owner who holds
# ``flow:execute`` must still run — the stored graph, not their override.
# --------------------------------------------------------------------------- #


class _Flow:
    def __init__(self, owner_id):
        self.id = uuid4()
        self.user_id = owner_id
        self.workspace_id = None
        self.folder_id = None


class _User:
    def __init__(self):
        self.id = uuid4()
        self.is_superuser = False


@pytest.fixture
def _reset_override_context():
    from langflow.services.authorization import flow_data_override

    token = flow_data_override._flow_data_override_allowed.set(False)
    yield
    flow_data_override._flow_data_override_allowed.reset(token)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_reset_override_context")
async def test_owner_override_is_resolved_without_consulting_policy(monkeypatch):
    """An owner is decided by ownership alone; the policy plugin is never consulted."""
    from langflow.services.authorization import flow_data_override

    called = False

    async def _never(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(flow_data_override, "ensure_flow_permission", _never)

    user = _User()
    flow = _Flow(owner_id=user.id)

    assert await flow_data_override.resolve_flow_data_override(user, flow) is True
    assert called is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("_reset_override_context")
async def test_write_holder_may_override_someone_elses_flow(monkeypatch):
    """``flow:write`` already allows persisting that graph, so running it grants nothing new."""
    from langflow.services.authorization import flow_data_override

    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_data_override, "ensure_flow_permission", _allow)

    assert await flow_data_override.resolve_flow_data_override(_User(), _Flow(owner_id=uuid4())) is True
    assert flow_data_override.flow_data_override_allowed() is True


@pytest.mark.asyncio
@pytest.mark.usefixtures("_reset_override_context")
async def test_execute_only_caller_may_not_override(monkeypatch):
    """Holding execute but not write leaves the stored definition in charge."""
    from langflow.services.authorization import flow_data_override

    async def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="nope")

    monkeypatch.setattr(flow_data_override, "ensure_flow_permission", _deny)

    assert await flow_data_override.resolve_flow_data_override(_User(), _Flow(owner_id=uuid4())) is False
    assert flow_data_override.flow_data_override_allowed() is False


@pytest.mark.usefixtures("_reset_override_context")
def test_execute_only_run_keeps_going_with_the_stored_graph():
    """The regression itself: this used to be a 404 that said the flow does not exist."""
    from langflow.api.v2.workflow_validation import _apply_flow_data_override_policy
    from lfx.workflow.converters import ParsedWorkflowRun

    user = _User()
    flow = _Flow(owner_id=uuid4())
    parsed = ParsedWorkflowRun(
        flow_id=str(flow.id),
        data={"nodes": [{"id": "injected"}], "edges": []},
        tweaks={"Component": {"model_name": "attacker-chosen"}},
    )

    result = _apply_flow_data_override_policy(parsed, flow, user)

    assert result.data is None
    assert result.tweaks == {}
    # Everything the caller is entitled to send survives.
    assert result.flow_id == str(flow.id)


@pytest.mark.usefixtures("_reset_override_context")
def test_owner_keeps_their_unsaved_canvas():
    """The owner's debugging workflow is untouched."""
    from langflow.api.v2.workflow_validation import _apply_flow_data_override_policy
    from lfx.workflow.converters import ParsedWorkflowRun

    user = _User()
    flow = _Flow(owner_id=user.id)
    data = {"nodes": [{"id": "mine"}], "edges": []}
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), data=data)

    assert _apply_flow_data_override_policy(parsed, flow, user).data == data


@pytest.mark.usefixtures("_reset_override_context")
def test_a_run_with_no_override_is_untouched():
    """A plain run carries no override, so there is nothing to strip."""
    from langflow.api.v2.workflow_validation import _apply_flow_data_override_policy
    from lfx.workflow.converters import ParsedWorkflowRun

    parsed = ParsedWorkflowRun(flow_id="abc", input_value="hello")

    assert _apply_flow_data_override_policy(parsed, _Flow(owner_id=uuid4()), _User()) is parsed


# --------------------------------------------------------------------------- #
# Round 2, finding 1: every row is classifiable, so a reader can ask for the
# actions people performed without losing rows written before classification.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_event_class_filter_selects_and_never_hides_untagged_rows():
    """The ``details.event`` filter the audit route applies, against a real database."""
    import sqlalchemy as sa
    from langflow.services.database.models.auth.authz import AuthzAuditLog
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import col, or_, select
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: AuthzAuditLog.metadata.create_all(c, tables=[AuthzAuditLog.__table__]))

    seeded = (
        ("share:create", {"event": audit_module.AUDIT_EVENT_DECISION}),
        ("share:create", {"event": audit_module.AUDIT_EVENT_MUTATION}),
        ("audit:read", {"event": audit_module.AUDIT_EVENT_ACCESS}),
        ("flow:read", None),
        ("flow:write", {"domain": "*"}),
    )
    async with AsyncSession(engine) as session:
        for action, details in seeded:
            session.add(
                AuthzAuditLog(
                    id=uuid4(),
                    timestamp=datetime.now(timezone.utc),
                    action=action,
                    resource_type=action.split(":")[0],
                    result=audit_module.AUDIT_ALLOW,
                    details=details,
                )
            )
        await session.commit()

        event_class = col(AuthzAuditLog.details)["event"].as_string()

        async def actions(stmt):
            return sorted(row.action for row in (await session.exec(stmt)).all())

        # Asking for what happened returns only the mutation.
        assert await actions(select(AuthzAuditLog).where(event_class.in_([audit_module.AUDIT_EVENT_MUTATION]))) == [
            "share:create"
        ]

        # Hiding permission checks drops the check and keeps every other row,
        # including the two written before classification existed.
        hide_checks = select(AuthzAuditLog).where(
            or_(event_class.not_in([audit_module.AUDIT_EVENT_DECISION]), event_class.is_(None)),
            col(AuthzAuditLog.action).not_in(["audit:read"]),
        )
        assert await actions(hide_checks) == ["flow:read", "flow:write", "share:create"]

        # The count the route reports comes off the same filtered subquery, so
        # pagination cannot disagree with the rows.
        total = int((await session.exec(select(sa.func.count()).select_from(hide_checks.subquery()))).first() or 0)
        assert total == 3

    await engine.dispose()
