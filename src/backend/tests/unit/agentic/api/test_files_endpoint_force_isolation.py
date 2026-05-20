"""B1 — /agentic/files must isolate users even under AUTO_LOGIN=True.

The existing endpoint suite pins AUTO_LOGIN=False globally; this file
covers the missing AUTO_LOGIN=True branch (the platform default) and
proves the cross-user IDOR documented in the review is closed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from langflow.agentic.api.files_router import get_file

if TYPE_CHECKING:
    from pathlib import Path


def _make_user(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=user_id)


@pytest.fixture
def auto_login_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pin AUTO_LOGIN=True per-instance + point at a fresh tmp_path."""
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: True,  # noqa: ARG005
    )
    return tmp_path


def _simulate_agent_write(user_id: str, relative: str, content: bytes) -> None:
    """Write the way the agent's write tools will after B1 wiring.

    force_isolation=True + bound user_id, so the file lands in users/<hash>/.
    """
    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    fs = FileSystemToolComponent()
    fs._user_id = user_id
    fs._force_isolation = True
    root = fs._validate_root()
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


class TestEndpointIsolatesUsersUnderAutoLogin:
    @pytest.mark.asyncio
    async def test_should_return_404_when_user_b_requests_user_a_file(self, auto_login_sandbox):  # noqa: ARG002
        # Arrange — Alice owns the file (agent-simulated write).
        _simulate_agent_write("user-alice", "secret.md", b"alice-owned")

        # Act — Bob asks the endpoint for the same path.
        bob = _make_user("user-bob")
        with pytest.raises(HTTPException) as exc:
            await get_file(path="secret.md", download=False, current_user=bob)

        # Assert — the endpoint must NOT serve another user's file. 404 (not
        # 403) keeps namespace existence opaque, matching the existing policy.
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_should_return_file_when_owner_requests_own_file(self, auto_login_sandbox):  # noqa: ARG002
        _simulate_agent_write("user-alice", "notes.md", b"# Alice notes\n")

        alice = _make_user("user-alice")
        response = await get_file(path="notes.md", download=False, current_user=alice)

        assert response.status_code == 200
        assert response.body == b"# Alice notes\n"
