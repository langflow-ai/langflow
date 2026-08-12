"""Warm FlowRead resolution without re-selecting executable graph data."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v2 import workflow as workflow_mod
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.warm_registry import resolver as resolver_mod


def _snapshot(
    *,
    flow_id: UUID,
    owner_id: UUID,
    endpoint_name: str,
    name: str,
    marker: str,
) -> FlowRead:
    return FlowRead(
        id=flow_id,
        name=name,
        data={"nodes": [], "edges": [], "marker": marker},
        user_id=owner_id,
        folder_id=None,
        workspace_id=None,
        endpoint_name=endpoint_name,
        updated_at=datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
    )


def _revision(flow: FlowRead) -> tuple[object, ...]:
    return (
        resolver_mod.flow_version(flow.updated_at),
        flow.name,
        flow.user_id,
        flow.workspace_id,
        flow.folder_id,
        flow.endpoint_name,
        flow.webhook,
        flow.access_type,
        flow.mcp_enabled,
        flow.flow_type,
        flow.a2a_enabled,
    )


def _metadata_row(flow: FlowRead) -> tuple[object, ...]:
    revision = _revision(flow)
    return (flow.updated_at, *revision[1:])


class _FakeRegistry:
    def __init__(self, snapshots: list[FlowRead]) -> None:
        self.snapshots = {str(flow.id): flow for flow in snapshots}
        self.aliases = {(str(flow.user_id), flow.endpoint_name): str(flow.id) for flow in snapshots}
        self.revisions = {str(flow.id): _revision(flow) for flow in snapshots}
        self.endpoint_lookups: list[tuple[str, str]] = []
        self.evictions: list[tuple[str, tuple[object, ...]]] = []

    def get_flow(self, flow_id: str) -> FlowRead | None:
        resolved = self.get_flow_with_revision(flow_id)
        return resolved[0] if resolved is not None else None

    def get_flow_with_revision(self, flow_id: str) -> tuple[FlowRead, tuple[object, ...]] | None:
        flow = self.snapshots.get(flow_id)
        revision = self.revisions.get(flow_id)
        if flow is None or revision is None:
            return None
        return flow.model_copy(deep=True), revision

    def get_flow_by_endpoint(self, user_id: object, endpoint_name: str) -> FlowRead | None:
        resolved = self.get_flow_by_endpoint_with_revision(user_id, endpoint_name)
        return resolved[0] if resolved is not None else None

    def get_flow_by_endpoint_with_revision(
        self,
        user_id: object,
        endpoint_name: str,
    ) -> tuple[FlowRead, tuple[object, ...]] | None:
        owner_id = str(user_id)
        self.endpoint_lookups.append((owner_id, endpoint_name))
        flow_id = self.aliases.get((owner_id, endpoint_name))
        return self.get_flow_with_revision(flow_id) if flow_id is not None else None

    def get_entry_revision(self, flow_id: str) -> tuple[object, ...] | None:
        return self.revisions.get(flow_id)

    async def evict_if_revision(self, flow_id: str, revision: tuple[object, ...]) -> bool:
        self.evictions.append((flow_id, revision))
        if self.revisions.get(flow_id) != revision:
            return False
        self.revisions.pop(flow_id, None)
        self.snapshots.pop(flow_id, None)
        return True


class _Result:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    def first(self):
        return self.row


class _Session:
    def __init__(self, rows: list[tuple[object, ...] | None]) -> None:
        self.rows = rows
        self.statements = []

    async def exec(self, statement):
        self.statements.append(statement)
        return _Result(self.rows.pop(0))


class _Scope:
    def __init__(self, session: _Session) -> None:
        self.session = session

    async def __aenter__(self) -> _Session:
        return self.session

    async def __aexit__(self, *_args) -> None:
        return None


def _install_resolver_fakes(monkeypatch, registry: _FakeRegistry, session: _Session) -> None:
    monkeypatch.setattr(resolver_mod, "_warm_registry_active", lambda: True)
    monkeypatch.setattr(resolver_mod, "get_warm_registry", lambda: registry)
    monkeypatch.setattr(resolver_mod, "session_scope", lambda: _Scope(session))


async def test_owner_uuid_hit_selects_only_metadata_and_skips_full_helper(monkeypatch):
    owner_id = uuid4()
    cached = _snapshot(
        flow_id=uuid4(),
        owner_id=owner_id,
        endpoint_name="shared-name",
        name="Owner flow",
        marker="cached",
    )
    registry = _FakeRegistry([cached])
    session = _Session([_metadata_row(cached)])
    _install_resolver_fakes(monkeypatch, registry, session)
    full_resolver = AsyncMock()
    monkeypatch.setattr(workflow_mod, "get_flow_by_id_or_endpoint_name", full_resolver)

    resolved = await workflow_mod.resolve_flow_for_execution(
        str(cached.id),
        SimpleNamespace(id=owner_id),
    )

    assert resolved == cached
    assert resolved is not cached
    assert resolved.data is not cached.data
    full_resolver.assert_not_awaited()
    selected_fields = set(session.statements[0].selected_columns.keys())
    assert "data" not in selected_fields
    assert selected_fields == {
        "updated_at",
        "name",
        "user_id",
        "workspace_id",
        "folder_id",
        "endpoint_name",
        "webhook",
        "access_type",
        "mcp_enabled",
        "flow_type",
        "a2a_enabled",
    }


async def test_same_endpoint_name_is_resolved_in_each_owner_namespace(monkeypatch):
    owner_a = uuid4()
    owner_b = uuid4()
    flow_a = _snapshot(flow_id=uuid4(), owner_id=owner_a, endpoint_name="same", name="A", marker="a")
    flow_b = _snapshot(flow_id=uuid4(), owner_id=owner_b, endpoint_name="same", name="B", marker="b")
    registry = _FakeRegistry([flow_a, flow_b])
    session = _Session([_metadata_row(flow_a), _metadata_row(flow_b)])
    _install_resolver_fakes(monkeypatch, registry, session)

    resolved_a = await resolver_mod.resolve_warm_flow_for_execution("same", owner_a)
    resolved_b = await resolver_mod.resolve_warm_flow_for_execution("same", owner_b)

    assert resolved_a.id == flow_a.id
    assert resolved_b.id == flow_b.id
    assert registry.endpoint_lookups == [(str(owner_a), "same"), (str(owner_b), "same")]


async def test_cross_owner_uuid_with_oss_authz_falls_back_to_private_404(monkeypatch):
    owner_id = uuid4()
    caller_id = uuid4()
    cached = _snapshot(flow_id=uuid4(), owner_id=owner_id, endpoint_name="private", name="Private", marker="cached")
    registry = _FakeRegistry([cached])
    session = _Session([])
    _install_resolver_fakes(monkeypatch, registry, session)
    authz = SimpleNamespace(
        is_enabled=AsyncMock(return_value=False),
        supports_cross_user_fetch=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(resolver_mod, "get_authorization_service", lambda: authz)
    full_resolver = AsyncMock(
        side_effect=HTTPException(status_code=404, detail=f"Flow identifier {cached.id} not found")
    )
    monkeypatch.setattr(workflow_mod, "get_flow_by_id_or_endpoint_name", full_resolver)

    with pytest.raises(HTTPException) as exc:
        await workflow_mod.resolve_flow_for_execution(str(cached.id), SimpleNamespace(id=caller_id))

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "FLOW_NOT_FOUND"
    full_resolver.assert_awaited_once_with(str(cached.id), caller_id, widen_for_shares=True)
    assert session.statements == []
    assert registry.evictions == []


async def test_share_aware_cross_owner_uuid_validates_metadata_then_returns_snapshot(monkeypatch):
    owner_id = uuid4()
    caller_id = uuid4()
    shared = _snapshot(flow_id=uuid4(), owner_id=owner_id, endpoint_name="shared", name="Shared", marker="cached")
    registry = _FakeRegistry([shared])
    session = _Session([_metadata_row(shared)])
    _install_resolver_fakes(monkeypatch, registry, session)
    authz = SimpleNamespace(
        is_enabled=AsyncMock(return_value=True),
        supports_cross_user_fetch=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(resolver_mod, "get_authorization_service", lambda: authz)

    resolved = await resolver_mod.resolve_warm_flow_for_execution(str(shared.id), caller_id, widen_for_shares=True)

    assert resolved == shared
    authz.is_enabled.assert_awaited_once()
    authz.supports_cross_user_fetch.assert_awaited_once()


async def test_shared_uuid_never_pairs_old_snapshot_with_new_revision(monkeypatch):
    """A reconcile during async authz checks must not return the superseded payload."""
    owner_id = uuid4()
    caller_id = uuid4()
    cached = _snapshot(flow_id=uuid4(), owner_id=owner_id, endpoint_name="shared", name="Old", marker="old")
    current = cached.model_copy(
        update={
            "name": "New",
            "data": {"nodes": [], "edges": [], "marker": "new"},
            "updated_at": datetime(2026, 8, 5, 13, tzinfo=timezone.utc),
        },
        deep=True,
    )
    registry = _FakeRegistry([cached])
    session = _Session([_metadata_row(current)])
    _install_resolver_fakes(monkeypatch, registry, session)

    async def _enable_and_reconcile() -> bool:
        registry.snapshots[str(current.id)] = current
        registry.revisions[str(current.id)] = _revision(current)
        return True

    authz = SimpleNamespace(
        is_enabled=AsyncMock(side_effect=_enable_and_reconcile),
        supports_cross_user_fetch=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(resolver_mod, "get_authorization_service", lambda: authz)

    resolved = await resolver_mod.resolve_warm_flow_for_execution(str(cached.id), caller_id, widen_for_shares=True)

    assert resolved is None
    assert registry.snapshots[str(current.id)].data["marker"] == "new"
    assert registry.evictions == [(str(cached.id), _revision(cached))]


async def test_metadata_mismatch_evicts_observed_revision_and_falls_back(monkeypatch):
    owner_id = uuid4()
    cached = _snapshot(flow_id=uuid4(), owner_id=owner_id, endpoint_name="renamed", name="Old", marker="cached")
    current = cached.model_copy(update={"name": "New"}, deep=True)
    registry = _FakeRegistry([cached])
    session = _Session([_metadata_row(current)])
    _install_resolver_fakes(monkeypatch, registry, session)
    full_resolver = AsyncMock(return_value=current)
    monkeypatch.setattr(workflow_mod, "get_flow_by_id_or_endpoint_name", full_resolver)

    resolved = await workflow_mod.resolve_flow_for_execution(
        str(cached.id),
        SimpleNamespace(id=owner_id),
    )

    assert resolved.name == "New"
    assert registry.evictions == [(str(cached.id), _revision(cached))]
    full_resolver.assert_awaited_once_with(str(cached.id), owner_id, widen_for_shares=True)


async def test_share_aware_non_owner_endpoint_uses_full_resolver(monkeypatch):
    owner_id = uuid4()
    caller_id = uuid4()
    shared = _snapshot(flow_id=uuid4(), owner_id=owner_id, endpoint_name="ambiguous", name="Shared", marker="cached")
    registry = _FakeRegistry([shared])
    session = _Session([])
    _install_resolver_fakes(monkeypatch, registry, session)
    full_resolver = AsyncMock(return_value=shared)
    monkeypatch.setattr(workflow_mod, "get_flow_by_id_or_endpoint_name", full_resolver)

    resolved = await workflow_mod.resolve_flow_for_execution(
        "ambiguous",
        SimpleNamespace(id=caller_id),
    )

    assert resolved.id == shared.id
    assert registry.endpoint_lookups == [(str(caller_id), "ambiguous")]
    assert session.statements == []
    full_resolver.assert_awaited_once_with("ambiguous", caller_id, widen_for_shares=True)
