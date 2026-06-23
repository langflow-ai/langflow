"""Tests for lfx.memory dispatch through the pluggable MEMORY_SERVICE.

Original bug: when langflow was installed alongside lfx but `lfx run` had only a
NoopDatabaseService registered, `lfx.memory` routed to `langflow.memory` simply
because the `langflow` package was importable, and its DB-backed code then hit a
NoopSession (silent no-op inserts / "Message with id X not found" on update).

The fix moved dispatch behind MEMORY_SERVICE: `lfx.memory` resolves the registered
memory service via `get_memory_service()` at call time and no longer asks "is
langflow importable and is its DB non-noop". The DB-vs-in-memory decision lives in
the memory service factory/service layer. These tests pin that contract.
"""

from __future__ import annotations

import uuid

import pytest
from lfx.services.database.service import NoopDatabaseService
from lfx.utils.langflow_utils import has_langflow_db_backend


class _FakeRealDbService:
    """Stand-in for any non-noop DatabaseService implementation."""


class TestHasLangflowDbBackend:
    """The util still exists (used by the factory layer); it is no longer the memory gate."""

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
    def test_memory_module_does_not_import_db_backend_gate(self):
        """The layering fix: memory/__init__ no longer references has_langflow_db_backend."""
        import lfx.memory as memory_mod

        assert not hasattr(memory_mod, "has_langflow_db_backend")

    def test_impl_resolves_registered_memory_service(self, monkeypatch):
        """_impl() routes to whatever get_memory_service() returns — at call time."""
        import lfx.memory as memory_mod

        sentinel = object()
        monkeypatch.setattr("lfx.memory.get_memory_service", lambda: sentinel)
        assert memory_mod._impl() is sentinel

    def test_impl_is_evaluated_per_call(self, monkeypatch):
        """Dispatch reads the registry each call, not a value cached at import."""
        import lfx.memory as memory_mod

        state = {"svc": object()}
        monkeypatch.setattr("lfx.memory.get_memory_service", lambda: state["svc"])

        first = memory_mod._impl()
        assert first is state["svc"]

        state["svc"] = object()
        assert memory_mod._impl() is state["svc"]
        assert memory_mod._impl() is not first

    def test_public_functions_route_through_service(self, monkeypatch):
        """Public proxies forward to the resolved service's matching method."""
        import lfx.memory as memory_mod

        calls = {}

        class _Recorder:
            async def astore_message(self, *args, **kwargs):
                calls["astore_message"] = (args, kwargs)
                return ["ok"]

            async def adelete_message(self, *args, **kwargs):
                calls["adelete_message"] = (args, kwargs)

        monkeypatch.setattr("lfx.memory.get_memory_service", lambda: _Recorder())

        import asyncio

        assert asyncio.run(memory_mod.astore_message("m", flow_id="f")) == ["ok"]
        assert calls["astore_message"] == (("m",), {"flow_id": "f"})

        # delete_message proxies to the service's adelete_message primitive.
        asyncio.run(memory_mod.delete_message("the-id"))
        assert calls["adelete_message"] == (("the-id",), {})


class TestAupdateMessagesRegression:
    """The original 'Message with id X not found' crash must not return."""

    @pytest.mark.asyncio
    async def test_aupdate_messages_does_not_raise_against_noop_db(self, monkeypatch):
        """With only a NoopDatabaseService, update upserts in-memory and succeeds."""
        try:
            from langflow.schema.message import Message
        except ImportError:
            from lfx.schema.message import Message

        # Force the noop-DB branch even if a real DB is registered in this env.
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
