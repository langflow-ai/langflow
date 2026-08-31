"""Tests for the assistant restore-point service.

``create_restore_point`` snapshots the flow via the existing flow-versioning
CRUD before a canvas-mutating assistant turn. It must be best-effort: any
failure returns None instead of raising so the turn never breaks.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.services.restore_point import (
    RESTORE_POINT_DESCRIPTION_PREFIX,
    create_restore_point,
)

FLOW_ID = str(uuid4())
USER_ID = str(uuid4())

CANVAS_DATA = {"nodes": [{"id": "n1"}], "edges": [{"id": "e1"}], "viewport": {}}


def _make_session(flow, latest_version=None):
    session = MagicMock()
    session.get = AsyncMock(return_value=flow)
    exec_result = MagicMock()
    exec_result.first.return_value = latest_version
    session.exec = AsyncMock(return_value=exec_result)
    return session


def _scope_for(session):
    @asynccontextmanager
    async def scope():
        yield session

    return scope


def _make_flow(data=None, user_id=USER_ID):
    from uuid import UUID

    return SimpleNamespace(data=data if data is not None else CANVAS_DATA, user_id=UUID(user_id) if user_id else None)


CRUD_TARGET = "langflow.services.database.models.flow_version.crud.create_flow_version_entry"
SCOPE_TARGET = "lfx.services.deps.session_scope"


class TestSkipConditions:
    @pytest.mark.asyncio
    async def test_should_return_none_when_flow_id_or_user_id_missing(self):
        assert await create_restore_point(None, USER_ID) is None
        assert await create_restore_point(FLOW_ID, None) is None
        assert await create_restore_point("", "") is None

    @pytest.mark.asyncio
    async def test_should_return_none_for_invalid_uuids(self):
        assert await create_restore_point("not-a-uuid", USER_ID) is None
        assert await create_restore_point(FLOW_ID, "not-a-uuid") is None

    @pytest.mark.asyncio
    async def test_should_skip_empty_canvas(self):
        flow = _make_flow(data={"nodes": [], "edges": [], "viewport": {}})
        session = _make_session(flow)
        create_entry = AsyncMock()

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            assert await create_restore_point(FLOW_ID, USER_ID) is None

        create_entry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_should_skip_missing_flow_or_no_data(self):
        session = _make_session(None)
        create_entry = AsyncMock()

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            assert await create_restore_point(FLOW_ID, USER_ID) is None

        create_entry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_should_skip_flow_owned_by_another_user(self):
        flow = _make_flow(user_id=str(uuid4()))
        session = _make_session(flow)
        create_entry = AsyncMock()

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            assert await create_restore_point(FLOW_ID, USER_ID) is None

        create_entry.assert_not_awaited()


class TestDuplicateSkip:
    @pytest.mark.asyncio
    async def test_should_return_existing_version_id_when_latest_matches_canvas(self):
        existing_id = uuid4()
        latest = SimpleNamespace(id=existing_id, data=CANVAS_DATA)
        session = _make_session(_make_flow(), latest_version=latest)
        create_entry = AsyncMock()

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            result = await create_restore_point(FLOW_ID, USER_ID)

        assert result == str(existing_id)
        create_entry.assert_not_awaited()


class TestCreation:
    @pytest.mark.asyncio
    async def test_should_create_version_with_assistant_description(self):
        new_id = uuid4()
        stale = SimpleNamespace(id=uuid4(), data={"nodes": [{"id": "old"}], "edges": []})
        session = _make_session(_make_flow(), latest_version=stale)
        create_entry = AsyncMock(return_value=SimpleNamespace(id=new_id))

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            result = await create_restore_point(FLOW_ID, USER_ID)

        assert result == str(new_id)
        create_entry.assert_awaited_once()
        kwargs = create_entry.await_args.kwargs
        assert kwargs["data"] == CANVAS_DATA
        assert kwargs["description"].startswith(RESTORE_POINT_DESCRIPTION_PREFIX)

    @pytest.mark.asyncio
    async def test_should_create_first_version_when_none_exist(self):
        new_id = uuid4()
        session = _make_session(_make_flow(), latest_version=None)
        create_entry = AsyncMock(return_value=SimpleNamespace(id=new_id))

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            result = await create_restore_point(FLOW_ID, USER_ID)

        assert result == str(new_id)

    @pytest.mark.asyncio
    async def test_should_snapshot_unowned_flow(self):
        """AUTO_LOGIN/shared flows have user_id=None — snapshot proceeds like the summary loader."""
        new_id = uuid4()
        session = _make_session(_make_flow(user_id=None), latest_version=None)
        create_entry = AsyncMock(return_value=SimpleNamespace(id=new_id))

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            assert await create_restore_point(FLOW_ID, USER_ID) == str(new_id)


class TestFailureTolerance:
    @pytest.mark.asyncio
    async def test_should_return_none_when_session_scope_raises(self):
        @asynccontextmanager
        async def broken_scope():
            msg = "db down"
            raise RuntimeError(msg)
            yield

        with patch(SCOPE_TARGET, broken_scope):
            assert await create_restore_point(FLOW_ID, USER_ID) is None

    @pytest.mark.asyncio
    async def test_should_return_none_when_version_creation_raises(self):
        session = _make_session(_make_flow(), latest_version=None)
        create_entry = AsyncMock(side_effect=RuntimeError("insert failed"))

        with patch(SCOPE_TARGET, _scope_for(session)), patch(CRUD_TARGET, create_entry):
            assert await create_restore_point(FLOW_ID, USER_ID) is None
