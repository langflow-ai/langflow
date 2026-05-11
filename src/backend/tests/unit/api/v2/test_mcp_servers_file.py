import io
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import UploadFile

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

    # Third upload with server config provided by user
    content3 = (
        b'{"mcpServers": {"everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}}}'
    )
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
async def test_concurrent_update_server_should_not_lose_servers(
    session, storage_service, settings_service, current_user
):
    """Concurrent update_server() calls must not silently drop servers.

    Bug: update_server() performs a non-atomic read-modify-write cycle on the
    MCP config file. When two calls overlap, both read the same stale config,
    modify independently, and the last write wins — silently losing the first
    call's server. This causes the E2E test
    'HTTP/SSE MCP server fields should persist after saving and editing'
    to fail because lf-starter_project gets wiped.
    """
    import asyncio
    import copy
    from unittest.mock import MagicMock, patch

    from langflow.api.v2.mcp import update_server

    # Shared mutable state simulating the MCP config file on disk
    config_state = {"mcpServers": {"server_a": {"command": "echo", "args": ["a"]}}}

    async def mock_get_server_list(*_args, **_kwargs):
        result = copy.deepcopy(config_state)
        await asyncio.sleep(0)  # Yield to allow interleaving between concurrent calls
        return result

    async def mock_upload_server_config(new_config, *_args, **_kwargs):
        await asyncio.sleep(0)  # Yield
        config_state["mcpServers"] = dict(new_config["mcpServers"])

    async def mock_get_server(name, *_args, **kwargs):
        server_list = kwargs.get("server_list", {})
        return server_list.get("mcpServers", {}).get(name)

    with patch.multiple(
        "langflow.api.v2.mcp",
        get_server_list=mock_get_server_list,
        upload_server_config=mock_upload_server_config,
        get_server=mock_get_server,
        get_shared_component_cache_service=MagicMock(return_value=SimpleNamespace()),
        safe_cache_get=MagicMock(return_value={}),
        safe_cache_set=MagicMock(),
    ):
        await asyncio.gather(
            update_server(
                "server_b",
                {"command": "echo", "args": ["b"]},
                current_user,
                session,
                storage_service,
                settings_service,
            ),
            update_server(
                "server_c",
                {"command": "echo", "args": ["c"]},
                current_user,
                session,
                storage_service,
                settings_service,
            ),
        )

    assert "server_a" in config_state["mcpServers"], "server_a was lost due to concurrent update_server race condition"
    assert "server_b" in config_state["mcpServers"], "server_b was lost due to concurrent update_server race condition"
    assert "server_c" in config_state["mcpServers"], "server_c was lost due to concurrent update_server race condition"
