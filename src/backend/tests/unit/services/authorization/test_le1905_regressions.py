"""Unit cover for the LE-1905 authorization-report fixes that live in OSS."""

from __future__ import annotations

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
