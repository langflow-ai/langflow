"""UC8 — POST /api/v1/agentic/sessions/reset endpoint.

Frontend calls this on every "new assistant session" boundary:
    - panel mounts with a fresh session_id
    - user clicks the New session button

The endpoint:
    - is authenticated (any unauthenticated request → 401, handled by
      the FastAPI dependency)
    - wipes the conversation buffer for the supplied session_id
    - wipes the user's registered components

We exercise the handler directly (not via TestClient) so the auth
dependency is bypassed via an injected ``current_user`` mock — mirrors
the test style of ``test_files_endpoint.py``.
"""

from __future__ import annotations

import secrets
import types
from typing import TYPE_CHECKING

import pytest
from langflow.agentic.services.conversation_buffer import (
    ConversationBuffer,
    ConversationTurn,
)
from langflow.agentic.services.user_components import (
    get_user_components_dir,
    register_user_component,
)

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import FloatInput, Output\n"
    "from lfx.schema import Data\n"
    "\n"
    "class SumComponent(Component):\n"
    "    inputs = [FloatInput(name='a'), FloatInput(name='b')]\n"
    "    outputs = [Output(name='result', display_name='Sum', method='run')]\n"
    "    def run(self) -> Data:\n"
    "        return Data(data={'sum': (self.a or 0) + (self.b or 0)})\n"
)


@pytest.fixture
def isolated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    (tmp_path / ".fs_pepper").write_bytes(secrets.token_bytes(32))

    from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

    monkeypatch.setattr(
        FileSystemToolComponent,
        "_resolve_auto_login",
        lambda self: False,  # noqa: ARG005
    )
    return tmp_path


@pytest.fixture
def fresh_conversation_buffer(monkeypatch: pytest.MonkeyPatch) -> ConversationBuffer:
    import langflow.agentic.services.conversation_buffer as module

    buf = ConversationBuffer()
    monkeypatch.setattr(module, "_singleton", buf)
    return buf


def _make_user(user_id: str = "user-alice"):
    """A lightweight stand-in for the FastAPI CurrentActiveUser dependency.

    The handler only reads ``current_user.id`` (string). A plain namespace
    keeps the test free of the SQLModel boilerplate.
    """
    return types.SimpleNamespace(id=user_id)


class TestResetSessionEndpointWipesComponents:
    async def test_should_delete_registered_components_for_calling_user(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        fresh_conversation_buffer: ConversationBuffer,  # noqa: ARG002
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        from langflow.agentic.api.sessions_router import reset_session

        result = await reset_session(
            current_user=_make_user("user-alice"),
            session_id="agentic_xxx",
        )

        assert result["components_cleared"] == 1
        components_dir = get_user_components_dir(user_id="user-alice")
        assert components_dir is not None
        assert list(components_dir.iterdir()) == []

    async def test_should_delete_conversation_buffer_for_session_id(
        self,
        isolated_sandbox: Path,  # noqa: ARG002 — fixture wires sandbox
        fresh_conversation_buffer: ConversationBuffer,
    ) -> None:
        fresh_conversation_buffer.push(
            "user-alice",
            "agentic_xxx",
            ConversationTurn(user="hi", assistant="hello"),
        )

        from langflow.agentic.api.sessions_router import reset_session

        await reset_session(
            current_user=_make_user("user-alice"),
            session_id="agentic_xxx",
        )

        assert fresh_conversation_buffer.get_recent("user-alice", "agentic_xxx") == []

    async def test_should_not_touch_other_users_components(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        fresh_conversation_buffer: ConversationBuffer,  # noqa: ARG002
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )
        bob_path = register_user_component(
            user_id="user-bob",
            class_name="BobSum",
            code=SAMPLE_CODE,
        )

        from langflow.agentic.api.sessions_router import reset_session

        await reset_session(
            current_user=_make_user("user-alice"),
            session_id="agentic_xxx",
        )

        # Bob's file untouched.
        assert bob_path.exists()

    async def test_should_not_touch_other_sessions_conversation_buffer(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        fresh_conversation_buffer: ConversationBuffer,
    ) -> None:
        fresh_conversation_buffer.push(
            "user-alice",
            "agentic_xxx",
            ConversationTurn(user="hi", assistant="ack"),
        )
        fresh_conversation_buffer.push(
            "user-alice",
            "agentic_yyy",
            ConversationTurn(user="other", assistant="other-ack"),
        )

        from langflow.agentic.api.sessions_router import reset_session

        await reset_session(
            current_user=_make_user("user-alice"),
            session_id="agentic_xxx",
        )

        # The other session is preserved.
        assert len(fresh_conversation_buffer.get_recent("user-alice", "agentic_yyy")) == 1


class TestResetSessionEndpointShape:
    async def test_should_accept_missing_session_id(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        fresh_conversation_buffer: ConversationBuffer,  # noqa: ARG002
    ) -> None:
        register_user_component(
            user_id="user-alice",
            class_name="SumComponent",
            code=SAMPLE_CODE,
        )

        from langflow.agentic.api.sessions_router import reset_session

        # session_id=None still wipes components (the "fresh mount with
        # a brand new id" scenario fires before any turns are logged —
        # the conversation buffer has nothing to clear).
        result = await reset_session(
            current_user=_make_user("user-alice"),
            session_id=None,
        )

        assert result["components_cleared"] == 1

    async def test_should_return_zero_counts_when_nothing_to_clear(
        self,
        isolated_sandbox: Path,  # noqa: ARG002
        fresh_conversation_buffer: ConversationBuffer,  # noqa: ARG002
    ) -> None:
        from langflow.agentic.api.sessions_router import reset_session

        result = await reset_session(
            current_user=_make_user("user-alice"),
            session_id="agentic_never-used",
        )

        assert result["components_cleared"] == 0
        # Conversation history clear is silent — endpoint reports the
        # components count, not a history count (history is unbounded
        # in shape; reporting a number is meaningless).
        assert "ok" in result.get("status", "").lower() or result.get("status") == "ok"
