"""Authorization regression tests for the voice flow-as-tool WebSocket."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1 import voice_mode


def _flow(*, owner_id, description="Authorized flow"):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=uuid4(),
        folder_id=uuid4(),
        description=description,
    )


class _DescriptionProbe:
    def __init__(self, *, owner_id):
        self.id = uuid4()
        self.user_id = owner_id
        self.workspace_id = uuid4()
        self.folder_id = uuid4()
        self.description_reads = 0

    @property
    def description(self):
        self.description_reads += 1
        return "private description"


@pytest.mark.asyncio
async def test_authorized_voice_flow_allows_owner(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    flow = _flow(owner_id=user.id)
    session = SimpleNamespace()
    read_flow = AsyncMock(return_value=flow)
    ensure_permission = AsyncMock()
    monkeypatch.setattr(voice_mode, "_read_flow", read_flow, raising=False)
    monkeypatch.setattr(voice_mode, "ensure_flow_permission", ensure_permission, raising=False)

    result = await voice_mode._get_authorized_voice_flow(str(flow.id), user, session)

    assert result is flow
    read_flow.assert_awaited_once_with(session, flow.id, user.id)
    ensure_permission.assert_awaited_once_with(
        user,
        voice_mode.FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )


@pytest.mark.asyncio
async def test_authorized_voice_flow_allows_share_aware_fetch_when_guard_allows(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    foreign_flow = _flow(owner_id=uuid4())
    session = SimpleNamespace()
    read_flow = AsyncMock(return_value=foreign_flow)
    ensure_permission = AsyncMock()
    monkeypatch.setattr(voice_mode, "_read_flow", read_flow, raising=False)
    monkeypatch.setattr(voice_mode, "ensure_flow_permission", ensure_permission, raising=False)

    result = await voice_mode._get_authorized_voice_flow(str(foreign_flow.id), user, session)

    assert result is foreign_flow
    read_flow.assert_awaited_once_with(session, foreign_flow.id, user.id)
    ensure_permission.assert_awaited_once_with(
        user,
        voice_mode.FlowAction.EXECUTE,
        flow_id=foreign_flow.id,
        flow_user_id=foreign_flow.user_id,
        workspace_id=foreign_flow.workspace_id,
        folder_id=foreign_flow.folder_id,
    )


@pytest.mark.asyncio
async def test_authorized_voice_flow_preserves_public_flow_access(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    public_flow = _flow(owner_id=uuid4())
    read_flow = AsyncMock(return_value=None)
    ensure_permission = AsyncMock()
    result = SimpleNamespace(first=lambda: public_flow)
    session = SimpleNamespace(exec=AsyncMock(return_value=result))
    monkeypatch.setattr(voice_mode, "_read_flow", read_flow, raising=False)
    monkeypatch.setattr(voice_mode, "ensure_flow_permission", ensure_permission, raising=False)

    authorized = await voice_mode._get_authorized_voice_flow(str(public_flow.id), user, session)

    assert authorized is public_flow
    session.exec.assert_awaited_once()
    ensure_permission.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_voice_flow_uses_same_generic_404(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    read_flow = AsyncMock(return_value=None)
    ensure_permission = AsyncMock()
    result = SimpleNamespace(first=lambda: None)
    session = SimpleNamespace(exec=AsyncMock(return_value=result))
    monkeypatch.setattr(voice_mode, "_read_flow", read_flow)
    monkeypatch.setattr(voice_mode, "ensure_flow_permission", ensure_permission)

    with pytest.raises(HTTPException) as exc_info:
        await voice_mode._get_authorized_voice_flow(str(uuid4()), user, session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Flow not found"
    ensure_permission.assert_not_awaited()


@pytest.mark.asyncio
async def test_denied_cross_user_websocket_reaches_no_description_connection_or_message_sink(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    foreign_flow = _DescriptionProbe(owner_id=uuid4())
    websocket = SimpleNamespace(accept=AsyncMock(), send_json=AsyncMock())
    legacy_description_sink = AsyncMock(return_value="private description")
    connect = Mock(side_effect=AssertionError("external connection reached before authorization"))
    add_message = AsyncMock()
    get_voice_config = Mock()

    monkeypatch.setattr(voice_mode, "get_current_user_for_websocket", AsyncMock(return_value=user))
    monkeypatch.setattr(
        voice_mode,
        "authenticate_and_get_openai_key",
        AsyncMock(return_value=(user, "test-openai-key")),
    )
    monkeypatch.setattr(voice_mode, "_read_flow", AsyncMock(return_value=foreign_flow), raising=False)
    monkeypatch.setattr(
        voice_mode,
        "ensure_flow_permission",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="denied")),
        raising=False,
    )
    # Pin the pre-fix unscoped description helper as an explicit sink: a deny
    # must return before either this legacy path or the Flow.description field.
    monkeypatch.setattr(voice_mode, "get_flow_desc_from_db", legacy_description_sink, raising=False)
    monkeypatch.setattr(voice_mode, "get_voice_config", get_voice_config)
    monkeypatch.setattr(voice_mode.websockets, "connect", connect)
    monkeypatch.setattr(voice_mode, "add_message_to_db", add_message)

    await voice_mode.flow_as_tool_websocket(
        client_websocket=websocket,
        flow_id=str(foreign_flow.id),
        background_tasks=BackgroundTasks(),
        session=SimpleNamespace(),
        session_id="voice-session",
    )

    websocket.accept.assert_awaited_once()
    websocket.send_json.assert_awaited_once_with({"error": "Failed to load flow: 404: Flow not found"})
    assert foreign_flow.description_reads == 0
    legacy_description_sink.assert_not_awaited()
    get_voice_config.assert_not_called()
    connect.assert_not_called()
    add_message.assert_not_awaited()
