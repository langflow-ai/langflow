import io
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException, UploadFile

# Module under test
from langflow.api.v2.files import upload_user_file
from langflow.api.v2.mcp import get_mcp_file

if TYPE_CHECKING:
    from langflow.services.database.models.file.model import File as UserFile


class FakeStorageService:  # Minimal stub for storage interactions
    def __init__(self):
        # key -> bytes
        self._store: dict[str, bytes] = {}

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False):
        key = f"{flow_id}/{file_name}"
        if append and key in self._store:
            self._store[key] += data
        else:
            self._store[key] = data

    async def get_file_size(self, flow_id: str, file_name: str):
        return len(self._store.get(f"{flow_id}/{file_name}", b""))

    async def delete_file(self, flow_id: str, file_name: str):
        self._store.pop(f"{flow_id}/{file_name}", None)


class FakeResult:  # Helper for Session.exec return
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class FakeSession:  # Minimal async session stub
    def __init__(self):
        self._db: dict[str, UserFile] = {}

    async def exec(self, stmt):
        # Extremely simplified: detect by LIKE pattern or equality against name/id
        # We only support SELECT UserFile WHERE name LIKE pattern or id equality
        stmt_str = str(stmt)
        if "user_file.name" in stmt_str:
            # LIKE pattern extraction
            pattern = stmt_str.split("like(")[-1].split(")")[0].strip('"%')
            rows = [f for name, f in self._db.items() if name.startswith(pattern)]
            return FakeResult(rows)
        if "user_file.id" in stmt_str:
            uid = stmt_str.split("=")[-1].strip().strip("'")
            rows = [f for f in self._db.values() if str(f.id) == uid]
            return FakeResult(rows)
        return FakeResult([])

    def add(self, obj):
        self._db[obj.name] = obj

    async def commit(self):
        return

    async def refresh(self, obj):  # noqa: ARG002
        return

    async def delete(self, obj):
        self._db.pop(obj.name, None)

    async def flush(self):
        return


class FakeSettings:
    max_file_size_upload: int = 10  # MB


@pytest.fixture
def current_user():
    class User(SimpleNamespace):
        id: str

    return User(id=str(uuid.uuid4()))


@pytest.fixture
def storage_service():
    return FakeStorageService()


@pytest.fixture
def settings_service():
    return SimpleNamespace(settings=FakeSettings())


@pytest.fixture
def session():
    return FakeSession()


@pytest.mark.asyncio
async def test_mcp_servers_upload_replace(session, storage_service, settings_service, current_user):
    """Uploading _mcp_servers.json twice should keep single DB record and no rename."""
    content1 = b'{"mcpServers": {}}'

    mcp_file_ext = await get_mcp_file(current_user, extension=True)
    mcp_file = await get_mcp_file(current_user)

    file1 = UploadFile(filename=mcp_file_ext, file=io.BytesIO(content1))
    file1.size = len(content1)

    # First upload
    await upload_user_file(
        file=file1,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    # DB should contain single entry named _mcp_servers
    assert list(session._db.keys()) == [mcp_file]

    # Upload again with different content
    content2 = b'{"mcpServers": {"everything": {}}}'
    file2 = UploadFile(filename=mcp_file_ext, file=io.BytesIO(content2))
    file2.size = len(content2)

    await upload_user_file(
        file=file2,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    # Still single record, same name
    assert list(session._db.keys()) == [mcp_file]

    record = session._db[mcp_file]
    # Storage path should match user_id/_mcp_servers.json
    expected_path = f"{current_user.id}/{mcp_file}.json"
    assert record.path == expected_path

    # Storage should have updated content
    stored_bytes = storage_service._store[expected_path]
    assert stored_bytes == content2

    # Third upload with an (allow-listed) server config provided by the user.
    content3 = b'{"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}'
    file3 = UploadFile(filename=mcp_file_ext, file=io.BytesIO(content3))
    file3.size = len(content3)

    await upload_user_file(
        file=file3,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    stored_bytes = storage_service._store[expected_path]
    assert stored_bytes == content3


@pytest.mark.asyncio
async def test_mcp_servers_upload_rejects_disallowed_command(session, storage_service, settings_service, current_user):
    """An uploaded MCP config with a disallowed command must be rejected (no stdio-spawn RCE).

    The upload path must enforce the same MCPServerConfig allow-list as the
    structured /api/v2/mcp/servers endpoints, so it can't be used to smuggle an
    arbitrary command that is later spawned via the stdio transport.
    """
    mcp_file_ext = await get_mcp_file(current_user, extension=True)

    malicious = b'{"mcpServers": {"evil": {"command": "/bin/sh; rm -rf /", "args": []}}}'
    file = UploadFile(filename=mcp_file_ext, file=io.BytesIO(malicious))
    file.size = len(malicious)

    with pytest.raises(HTTPException) as exc_info:
        await upload_user_file(
            file=file,
            session=session,
            current_user=current_user,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    assert exc_info.value.status_code == 422
    # Nothing should have been written to storage on rejection.
    assert storage_service._store == {}
    # And no database metadata record should have been created either, so a rejected
    # upload can't leave a dangling row behind (partial-write regression guard).
    assert session._db == {}


@pytest.mark.asyncio
async def test_mcp_servers_upload_rejects_not_valid_json(session, storage_service, settings_service, current_user):
    """A non-JSON upload to the MCP config path is rejected with 422 (validator JSON branch)."""
    mcp_file_ext = await get_mcp_file(current_user, extension=True)

    not_json = b"not json"
    file = UploadFile(filename=mcp_file_ext, file=io.BytesIO(not_json))
    file.size = len(not_json)

    with pytest.raises(HTTPException) as exc_info:
        await upload_user_file(
            file=file,
            session=session,
            current_user=current_user,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    assert exc_info.value.status_code == 422
    assert "not valid JSON" in exc_info.value.detail
    assert storage_service._store == {}
    assert session._db == {}


@pytest.mark.asyncio
async def test_mcp_servers_upload_rejects_non_object_mcpservers(
    session, storage_service, settings_service, current_user
):
    """An ``mcpServers`` value that isn't an object is rejected with 422 (validator shape branch)."""
    mcp_file_ext = await get_mcp_file(current_user, extension=True)

    bad_shape = b'{"mcpServers": "x"}'
    file = UploadFile(filename=mcp_file_ext, file=io.BytesIO(bad_shape))
    file.size = len(bad_shape)

    with pytest.raises(HTTPException) as exc_info:
        await upload_user_file(
            file=file,
            session=session,
            current_user=current_user,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    assert exc_info.value.status_code == 422
    assert "expected an 'mcpServers' object" in exc_info.value.detail
    assert storage_service._store == {}
    assert session._db == {}


@pytest.mark.asyncio
async def test_mcp_servers_upload_blocked_when_locked_for_non_superuser(session, storage_service, current_user):
    """A locked MCP config can't be replaced by a non-superuser via the file-upload path.

    The structured /api/v2/mcp/servers endpoints 403 non-superuser writes while locked,
    and this branch writes the same _mcp_servers_<uid>.json that get_server_list reads —
    so without the same guard the upload path would be a lock bypass.
    """
    locked_settings = SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=10, mcp_servers_locked=True))
    current_user.is_superuser = False

    mcp_file_ext = await get_mcp_file(current_user, extension=True)
    content = b'{"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}'
    file = UploadFile(filename=mcp_file_ext, file=io.BytesIO(content))
    file.size = len(content)

    with pytest.raises(HTTPException) as exc_info:
        await upload_user_file(
            file=file,
            session=session,
            current_user=current_user,
            storage_service=storage_service,
            settings_service=locked_settings,
        )

    assert exc_info.value.status_code == 403
    # The lock fires before any write, so nothing is persisted.
    assert storage_service._store == {}
    assert session._db == {}


@pytest.mark.asyncio
async def test_mcp_servers_upload_allowed_when_locked_for_superuser(session, storage_service, current_user):
    """A superuser can still replace the MCP config via upload while the lock is on."""
    locked_settings = SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=10, mcp_servers_locked=True))
    current_user.is_superuser = True

    mcp_file_ext = await get_mcp_file(current_user, extension=True)
    mcp_file = await get_mcp_file(current_user)
    content = b'{"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}'
    file = UploadFile(filename=mcp_file_ext, file=io.BytesIO(content))
    file.size = len(content)

    await upload_user_file(
        file=file,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=locked_settings,
    )

    expected_path = f"{current_user.id}/{mcp_file}.json"
    assert storage_service._store[expected_path] == content


@pytest.mark.asyncio
async def test_concurrent_update_server_should_not_lose_servers(tmp_path):
    """Concurrent update_server() calls must not silently drop servers.

    Formerly update_server() did a non-atomic read-modify-write on the MCP config
    file; overlapping calls read the same stale config and the last write won,
    silently losing a server. MCP servers are now one row per server in the
    mcp_server table (unique on (user_id, name)), so concurrent adds of different
    servers touch different rows and cannot lose each other — with no in-process
    lock. This is the regression guard for that lost-update bug.
    """
    import asyncio
    import uuid as uuid_lib
    from unittest.mock import MagicMock, patch

    import langflow.services.database.models  # noqa: F401  (register SQLModel tables)
    from langflow.api.v2.mcp import get_server_list, update_server
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    # File-backed DB so each concurrent session gets its own connection.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'mcp.db'}", connect_args={"timeout": 30})

    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    user = SimpleNamespace(id=uuid_lib.uuid4())

    async def add(name: str, val: str) -> None:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server(name, {"command": "echo", "args": [val]}, user, session, None, None)

    with patch.multiple(
        "langflow.api.v2.mcp",
        get_shared_component_cache_service=MagicMock(return_value=SimpleNamespace()),
        safe_cache_get=MagicMock(return_value={}),
        safe_cache_set=MagicMock(),
    ):
        await add("server_a", "a")
        await asyncio.gather(add("server_b", "b"), add("server_c", "c"))
        async with AsyncSession(engine, expire_on_commit=False) as session:
            servers = (await get_server_list(user, session, None, None))["mcpServers"]

    await engine.dispose()
    assert "server_a" in servers, "server_a was lost due to concurrent update_server race condition"
    assert "server_b" in servers, "server_b was lost due to concurrent update_server race condition"
    assert "server_c" in servers, "server_c was lost due to concurrent update_server race condition"


def test_enforce_immutable_server_name_rejects_mismatch():
    """A body name that differs from the URL name is an explicit 422, not a silent no-op."""
    from langflow.api.v2.mcp import _enforce_immutable_server_name

    with pytest.raises(HTTPException) as exc_info:
        _enforce_immutable_server_name("old-name", {"name": "new-name", "url": "http://localhost:9000"})

    assert exc_info.value.status_code == 422
    # The message names both the URL identifier and the rejected body value.
    assert "old-name" in exc_info.value.detail
    assert "new-name" in exc_info.value.detail


def test_enforce_immutable_server_name_strips_matching_name():
    """A redundant matching name is dropped so it never pollutes the stored config."""
    from langflow.api.v2.mcp import _enforce_immutable_server_name

    cleaned = _enforce_immutable_server_name("srv", {"name": "srv", "command": "npx", "args": ["-y", "x"]})

    assert cleaned == {"command": "npx", "args": ["-y", "x"]}
    assert "name" not in cleaned


def test_enforce_immutable_server_name_passthrough_without_name():
    """Configs without a name field are returned unchanged."""
    from langflow.api.v2.mcp import _enforce_immutable_server_name

    config = {"command": "npx", "args": ["-y", "x"]}

    assert _enforce_immutable_server_name("srv", config) == config


@pytest.mark.asyncio
async def test_patch_server_rejects_name_change(session, storage_service, settings_service, current_user):
    """PATCH with a body name different from the URL must 422 instead of silently no-op'ing.

    Regression: MCPServerConfig allows extra fields, so a ``name`` in the PATCH body was
    persisted as stray config and echoed in the 200 response, falsely implying a rename
    succeeded while the server stayed keyed under the original (URL) name.
    """
    from unittest.mock import AsyncMock, patch

    from langflow.api.v2.mcp import update_server_endpoint
    from langflow.api.v2.schemas import MCPServerConfig

    body = MCPServerConfig(name="new-name", url="http://localhost:9000")

    with (
        patch("langflow.api.v2.mcp.update_server", new=AsyncMock()) as mock_update,
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_server_endpoint(
            server_name="old-name",
            server_config=body,
            current_user=current_user,
            session=session,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    assert exc_info.value.status_code == 422
    mock_update.assert_not_called()  # guard fires before any write/upsert


@pytest.mark.asyncio
async def test_patch_server_strips_matching_name_before_persist(
    session, storage_service, settings_service, current_user
):
    """A PATCH body that echoes the URL name must not persist ``name`` as stray config."""
    from unittest.mock import AsyncMock, patch

    from langflow.api.v2.mcp import update_server_endpoint
    from langflow.api.v2.schemas import MCPServerConfig

    body = MCPServerConfig(name="srv", url="http://localhost:9000")

    with patch("langflow.api.v2.mcp.update_server", new=AsyncMock(return_value={"ok": True})) as mock_update:
        await update_server_endpoint(
            server_name="srv",
            server_config=body,
            current_user=current_user,
            session=session,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    # update_server is called positionally as (server_name, server_config_dict, ...).
    persisted_config = mock_update.call_args.args[1]
    assert persisted_config == {"url": "http://localhost:9000"}
    assert "name" not in persisted_config


@pytest.mark.asyncio
async def test_post_server_rejects_name_mismatch(session, storage_service, settings_service, current_user):
    """POST with a body name different from the URL must 422 (same guard as PATCH)."""
    from unittest.mock import AsyncMock, patch

    from langflow.api.v2.mcp import add_server
    from langflow.api.v2.schemas import MCPServerConfig

    body = MCPServerConfig(name="different", url="http://localhost:9000")

    with (
        patch("langflow.api.v2.mcp.update_server", new=AsyncMock()) as mock_update,
        pytest.raises(HTTPException) as exc_info,
    ):
        await add_server(
            server_name="intended-name",
            server_config=body,
            current_user=current_user,
            session=session,
            storage_service=storage_service,
            settings_service=settings_service,
        )

    assert exc_info.value.status_code == 422
    mock_update.assert_not_called()
