"""Regression tests for lfx.memory runtime dispatch.

Original bug: when langflow was installed alongside lfx but `lfx run` had
only a NoopDatabaseService registered, `lfx.memory` bound at import time to
`langflow.memory` (because the `langflow` package was importable). The
langflow-backed `aupdate_messages` then called `session.get(...)` on a
NoopSession, which always returns `None`, raising spurious
"Message with id X not found" errors mid-stream.
"""

from __future__ import annotations

import uuid

import pytest
from lfx.services.database.service import NoopDatabaseService
from lfx.utils.langflow_utils import has_langflow_db_backend


class _FakeRealDbService:
    """Stand-in for any non-noop DatabaseService implementation."""


class TestHasLangflowDbBackend:
    def test_returns_false_when_langflow_not_importable(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.langflow_utils.has_langflow_memory", lambda: False)
        assert has_langflow_db_backend() is False

    def test_returns_false_with_noop_db_service(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.langflow_utils.has_langflow_memory", lambda: True)
        monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: NoopDatabaseService())
        assert has_langflow_db_backend() is False

    def test_returns_true_with_real_db_service(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.langflow_utils.has_langflow_memory", lambda: True)
        monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: _FakeRealDbService())
        assert has_langflow_db_backend() is True

    def test_returns_false_when_get_db_service_raises(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.langflow_utils.has_langflow_memory", lambda: True)

        def boom():
            msg = "service manager exploded"
            raise RuntimeError(msg)

        monkeypatch.setattr("lfx.services.deps.get_db_service", boom)
        assert has_langflow_db_backend() is False


class TestMemoryDispatch:
    def test_dispatches_to_stubs_when_no_real_db(self, monkeypatch):
        import lfx.memory as memory_mod
        from lfx.memory import stubs

        monkeypatch.setattr("lfx.memory.has_langflow_db_backend", lambda: False)
        assert memory_mod._impl() is stubs

    def test_dispatches_to_langflow_when_real_db(self, monkeypatch):
        pytest.importorskip("langflow.memory")
        import langflow.memory as langflow_memory
        import lfx.memory as memory_mod

        monkeypatch.setattr("lfx.memory.has_langflow_db_backend", lambda: True)
        assert memory_mod._impl() is langflow_memory

    def test_dispatch_is_evaluated_per_call(self, monkeypatch):
        """Dispatch must read the backend state each call, not cache at import.

        The database service is often registered *after* lfx.memory is imported
        (components load first, services register during graph setup), so
        memoizing the dispatcher would bind to whatever state existed at
        component-module load time.
        """
        import lfx.memory as memory_mod
        from lfx.memory import stubs

        state = {"real": False}
        monkeypatch.setattr("lfx.memory.has_langflow_db_backend", lambda: state["real"])

        assert memory_mod._impl() is stubs
        state["real"] = True
        pytest.importorskip("langflow.memory")
        import langflow.memory as langflow_memory

        assert memory_mod._impl() is langflow_memory


class TestAupdateMessagesRegression:
    """Direct regression for the original 'Message with id X not found' crash."""

    @pytest.mark.asyncio
    async def test_aupdate_messages_does_not_raise_against_noop_session(self, monkeypatch):
        """Regression: route to stubs (no-op) instead of raising via langflow.memory.

        With langflow importable but only a NoopDatabaseService registered,
        aupdate_messages must route to stubs and succeed silently rather than
        trigger langflow.memory's strict existence check against NoopSession.
        """
        try:
            from langflow.schema.message import Message
        except ImportError:
            from lfx.schema.message import Message

        # Force the noop-DB branch even if a real DB happens to be registered in
        # this test environment.
        monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: NoopDatabaseService())

        from lfx.memory import aupdate_messages

        msg = Message(
            id=str(uuid.uuid4()),
            text="hello",
            sender="AI",
            sender_name="Test",
            session_id="test-session",
        )
        result = await aupdate_messages(msg)
        assert isinstance(result, list)
