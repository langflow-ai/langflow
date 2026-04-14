from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.services.database.models.flow_version.crud import (
    create_flow_version_entry,
    get_flow_version_list,
    has_deployment_attachments,
)


class _OneResult:
    def __init__(self, value):
        self._value = value

    def one(self):
        return self._value


class _AllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _AsyncNoopSavepoint:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_has_deployment_attachments_checks_live_deployment_join():
    db = AsyncMock()
    db.exec = AsyncMock(side_effect=[_OneResult(1)])

    result = await has_deployment_attachments(
        db,
        flow_version_id=uuid4(),
        user_id=uuid4(),
    )

    assert result is True
    # String-match on compiled SQL because these tests use mocked sessions
    # without a real database engine.
    statement_text = str(db.exec.await_args_list[0].args[0]).lower()
    assert "join deployment" in statement_text


@pytest.mark.asyncio
async def test_has_deployment_attachments_prunes_orphan_rows_when_no_live_attachment():
    db = AsyncMock()
    stale_attachment_id = uuid4()
    db.exec = AsyncMock(
        side_effect=[
            _OneResult(0),
            _AllResult([stale_attachment_id]),
            SimpleNamespace(rowcount=1),
        ]
    )

    result = await has_deployment_attachments(
        db,
        flow_version_id=uuid4(),
        user_id=uuid4(),
    )

    assert result is False
    assert db.exec.await_count == 3
    delete_statement_text = str(db.exec.await_args_list[2].args[0]).lower()
    assert "delete from flow_version_deployment_attachment" in delete_statement_text


@pytest.mark.asyncio
async def test_get_flow_version_list_marks_deployment_status_using_live_deployments_only():
    db = AsyncMock()
    db.exec = AsyncMock(return_value=_AllResult([(SimpleNamespace(id=uuid4()), True)]))

    rows = await get_flow_version_list(
        db,
        flow_id=uuid4(),
        user_id=uuid4(),
        deployment_ids=[uuid4()],
    )

    assert len(rows) == 1
    assert rows[0][1] is True
    statement_text = str(db.exec.await_args.args[0]).lower()
    assert "join deployment" in statement_text


@pytest.mark.asyncio
async def test_create_flow_version_entry_pruning_uses_live_deployment_join(monkeypatch):
    flow_id = uuid4()
    user_id = uuid4()

    monkeypatch.setattr(
        "langflow.services.database.models.flow_version.crud.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(max_flow_version_entries_per_flow=5)),
    )

    session = AsyncMock()
    session.exec = AsyncMock(
        side_effect=[
            _OneResult(None),  # max(version_number)
            SimpleNamespace(rowcount=0),  # prune delete
        ]
    )
    session.begin_nested = lambda: _AsyncNoopSavepoint()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    await create_flow_version_entry(
        session,
        flow_id=flow_id,
        user_id=user_id,
        data={"nodes": [], "edges": []},
    )

    prune_statement_text = str(session.exec.await_args_list[1].args[0]).lower()
    assert "join deployment" in prune_statement_text
