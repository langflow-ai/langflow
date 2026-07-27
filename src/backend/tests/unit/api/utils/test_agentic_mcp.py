"""Tests for the agentic MCP server removal helper.

``remove_agentic_mcp_server`` previously called ``update_server`` without
``delete=True`` under a comment claiming "Empty config removes the server". That
was never true: the call *replaced* the config with ``{}`` for users who had the
server, and — worse — *created* an empty-config ``langflow-agentic`` row for
users who never had it (the flag-less call takes the create path when no row
exists). These tests pin the corrected behavior against a real SQLite DB.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import langflow.services.database.models  # noqa: F401  (register SQLModel tables)
import pytest
from langflow.api.utils.mcp.agentic_mcp import remove_agentic_mcp_server
from langflow.api.v2.mcp import get_server_list, update_server
from langflow.services.database.models import MCPServer
from langflow.services.database.models.user.model import User
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

# _clear_server_cache() calls the shared component cache service, which isn't booted
# in a bare unit test; no-op it (orthogonal to the behavior under test).
CACHE_PATCH = {
    "get_shared_component_cache_service": MagicMock(return_value=SimpleNamespace()),
    "safe_cache_get": MagicMock(return_value={}),
    "safe_cache_set": MagicMock(),
}

# remove_agentic_mcp_server resolves storage/settings services at call time; neither
# is used by the DB-backed update_server, so plain mocks suffice.
SERVICE_PATCH = {
    "get_service": MagicMock(return_value=MagicMock()),
    "get_settings_service": MagicMock(return_value=MagicMock()),
}


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _add_user(session: AsyncSession, username: str) -> User:
    user = User(id=uuid.uuid4(), username=username, password="pw", is_active=True)  # noqa: S106
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_remove_agentic_mcp_server_removes_row():
    """Removal deletes the langflow-agentic row and leaves other servers untouched."""
    engine = await _engine()

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            user = await _add_user(session, "agentic_user")
            await update_server(
                "langflow-agentic",
                {"command": "python", "args": ["-m", "langflow.agentic.mcp"]},
                user,
                session,
                None,
                None,
            )
            await update_server("other", {"url": "https://example.com/mcp"}, user, session, None, None)

            with patch.multiple("langflow.api.utils.mcp.agentic_mcp", **SERVICE_PATCH):
                await remove_agentic_mcp_server(session)

            servers = (await get_server_list(user, session, None, None))["mcpServers"]

    await engine.dispose()
    assert "langflow-agentic" not in servers, f"agentic server must be removed, got {sorted(servers)}"
    assert "other" in servers, "removal must not touch unrelated servers"
    assert servers["other"] == {"url": "https://example.com/mcp"}


@pytest.mark.asyncio
async def test_remove_agentic_mcp_server_absent_is_noop():
    """A user without the server must not gain an empty-config row, and removal must not raise.

    The pre-fix flag-less call created a `langflow-agentic` row with `{}` config for such
    users (create path of update_server), surfacing a broken entry in the servers list.
    """
    engine = await _engine()

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            user = await _add_user(session, "no_server_user")

            with patch.multiple("langflow.api.utils.mcp.agentic_mcp", **SERVICE_PATCH):
                await remove_agentic_mcp_server(session)

            rows = (await session.exec(select(MCPServer).where(MCPServer.user_id == user.id))).all()

    await engine.dispose()
    assert rows == [], f"no row may be created for a user who never had the server, got {rows}"
