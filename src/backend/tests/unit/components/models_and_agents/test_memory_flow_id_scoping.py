"""Tests that MemoryComponent scopes chat history retrieval by flow_id.

Regression test for https://github.com/langflow-ai/langflow/issues/13059

Before the fix, ``MemoryComponent.retrieve_messages`` called
``aget_messages`` without ``flow_id``. Because the Langflow playground assigns
default session names (e.g. "New Session 0") that are not unique across flows,
this caused chat history from Flow A to leak into Flow B whenever both used
the same session name. The Agent component is affected because it delegates
its chat-history fetch to this method.

These tests assert that the call into ``aget_messages`` is now scoped by the
graph's ``flow_id`` (coerced to ``UUID``) so flows can no longer cross-read
each other's history.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from lfx.components.models_and_agents.memory import (
    MAX_CHAT_HISTORY_FETCH_LIMIT,
    MemoryComponent,
    _coerce_flow_id_to_uuid,
    aget_agent_chat_history,
)


def _build_component(
    flow_id: str | UUID | None,
    session_id: str = "session-shared",
) -> MemoryComponent:
    component = MemoryComponent()
    component.set(session_id=session_id, n_messages=10, order="Ascending")
    # ``Component.graph`` is a read-only property -> ``self._vertex.graph``,
    # so we wire the underlying ``_vertex`` instead of assigning ``graph``.
    component._vertex = SimpleNamespace(graph=SimpleNamespace(flow_id=flow_id, session_id=session_id))
    return component


class TestCoerceFlowIdToUuid:
    """Validate the small UUID-coercion helper used by retrieve_messages."""

    def test_returns_none_for_missing_values(self):
        assert _coerce_flow_id_to_uuid(None) is None
        assert _coerce_flow_id_to_uuid("") is None

    def test_passes_uuid_through_unchanged(self):
        value = uuid4()
        assert _coerce_flow_id_to_uuid(value) is value

    def test_parses_uuid_string(self):
        raw = "11111111-1111-1111-1111-111111111111"
        assert _coerce_flow_id_to_uuid(raw) == UUID(raw)

    def test_returns_none_for_invalid_string_and_does_not_raise(self):
        # Synthetic/test flow IDs may not be UUIDs; we must degrade gracefully.
        assert _coerce_flow_id_to_uuid("not-a-uuid") is None

    def test_invalid_flow_id_emits_structured_error_log(self):
        """Fallback to unscoped retrieval is a privacy regression — alert on it.

        See PR #13087 review I3: this path re-enables the cross-flow leak
        that issue #13059 closed. The log call uses ``error`` level + a
        structured ``event`` tag so observability pipelines can alert.
        """
        with patch("lfx.components.models_and_agents.memory.logger") as mock_logger:
            _coerce_flow_id_to_uuid("not-a-uuid")

        mock_logger.error.assert_called_once()
        call = mock_logger.error.call_args
        assert "memory_flow_id_unscoped" in call.args[0]
        assert call.kwargs.get("extra", {}).get("event") == "memory_flow_id_unscoped"


class TestRetrieveMessagesPassesFlowId:
    """The leak fix: retrieve_messages must pass flow_id to aget_messages."""

    @pytest.mark.asyncio
    async def test_passes_graph_flow_id_as_uuid(self):
        flow_id_str = "22222222-2222-2222-2222-222222222222"
        component = _build_component(flow_id=flow_id_str)

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await component.retrieve_messages()

        mock_get.assert_awaited_once()
        kwargs = mock_get.await_args.kwargs
        assert kwargs["flow_id"] == UUID(flow_id_str), (
            "retrieve_messages must scope by flow_id so default session names "
            "do not leak chat history across flows (issue #13059)."
        )
        assert kwargs["session_id"] == "session-shared"

    @pytest.mark.asyncio
    async def test_isolates_two_flows_sharing_a_session_name(self):
        """Reproduction of the leak: same session name, different flow_ids.

        Flow A and Flow B both use session ``New Session 0``. With the fix in
        place, the call into ``aget_messages`` is scoped by each flow's UUID,
        so the database query can no longer return cross-flow rows.
        """
        flow_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        flow_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        shared_session = "New Session 0"

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await _build_component(flow_id=flow_a, session_id=shared_session).retrieve_messages()
            await _build_component(flow_id=flow_b, session_id=shared_session).retrieve_messages()

        assert mock_get.await_count == 2
        first_call_kwargs = mock_get.await_args_list[0].kwargs
        second_call_kwargs = mock_get.await_args_list[1].kwargs
        assert first_call_kwargs["flow_id"] == UUID(flow_a)
        assert second_call_kwargs["flow_id"] == UUID(flow_b)
        # Same session name reaches the DB layer, but flow_id now disambiguates.
        assert first_call_kwargs["session_id"] == shared_session
        assert second_call_kwargs["session_id"] == shared_session

    @pytest.mark.asyncio
    async def test_falls_back_to_none_when_flow_id_missing(self):
        component = _build_component(flow_id=None)

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await component.retrieve_messages()

        assert mock_get.await_args.kwargs["flow_id"] is None

    @pytest.mark.asyncio
    async def test_falls_back_to_none_when_flow_id_is_not_a_uuid(self):
        """Tests with synthetic graph IDs must not crash retrieval."""
        component = _build_component(flow_id="not-a-uuid")

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await component.retrieve_messages()

        assert mock_get.await_args.kwargs["flow_id"] is None

    @pytest.mark.asyncio
    async def test_external_memory_path_is_untouched(self):
        """External Memory providers have no concept of flow_id; do not pass it."""

        class _FakeExternalMemory:
            session_id: str | None = None
            context_id: str | None = None

            async def aget_messages(self):
                return []

        component = _build_component(flow_id="33333333-3333-3333-3333-333333333333")
        component.set(memory=_FakeExternalMemory())

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await component.retrieve_messages()

        mock_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetches_desc_and_reverses_for_ascending_order(self):
        """PR #13087 review I2: avoid the >10k row ASC slice trap.

        Querying ``order=ASC, limit=MAX`` then slicing ``[-n:]`` would return
        the chronological FIRST window on huge sessions. We query DESC with
        the actual limit and reverse to the user-selected order, so the slice
        is always the genuine most-recent messages.
        """
        component = _build_component(flow_id="22222222-2222-2222-2222-222222222222")
        # MemoryComponent ``order`` defaults to Ascending in _build_component.
        # The mock returns DESC-ordered data (most recent first), as the DB would.
        desc_rows = [SimpleNamespace(id=f"msg-{i}") for i in (4, 3, 2, 1, 0)]
        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=desc_rows),
        ) as mock_get:
            result = await component.retrieve_messages()

        assert mock_get.await_args.kwargs["order"] == "DESC"
        assert mock_get.await_args.kwargs["limit"] == 10  # _build_component sets n_messages=10
        assert [m.id for m in result] == ["msg-0", "msg-1", "msg-2", "msg-3", "msg-4"]

    @pytest.mark.asyncio
    async def test_descending_order_passthrough_keeps_desc_view(self):
        component = _build_component(flow_id="22222222-2222-2222-2222-222222222222")
        component.set(order="Descending")
        desc_rows = [SimpleNamespace(id=f"msg-{i}") for i in (4, 3, 2, 1, 0)]
        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=desc_rows),
        ):
            result = await component.retrieve_messages()

        assert [m.id for m in result] == ["msg-4", "msg-3", "msg-2", "msg-1", "msg-0"]


class TestStoreMessagePassesFlowId:
    """PR #13087 review I1: write/read flow_id handling must be symmetric.

    The original PR protected ``retrieve_messages`` against ``self.graph``
    raising on ad-hoc instantiation but left ``store_message`` calling
    ``self.graph.flow_id`` directly — so a custom subclass or integration
    test would crash on the write path before reaching the safe read path.
    Both paths now go through ``_coerce_flow_id_to_uuid(_safe_graph_flow_id(self))``.
    """

    @pytest.mark.asyncio
    async def test_store_passes_coerced_flow_id_to_astore_and_aget(self):
        flow_id_str = "22222222-2222-2222-2222-222222222222"
        component = _build_component(flow_id=flow_id_str)
        component.set(mode="Store", message="hi", sender="User", sender_name="Tester")

        stored = SimpleNamespace(id="stored-1")
        with (
            patch(
                "lfx.components.models_and_agents.memory.astore_message",
                new=AsyncMock(return_value=None),
            ) as mock_store,
            patch(
                "lfx.components.models_and_agents.memory.aget_messages",
                new=AsyncMock(return_value=[stored]),
            ) as mock_get,
        ):
            await component.store_message()

        assert mock_store.await_args.kwargs["flow_id"] == UUID(flow_id_str)
        assert mock_get.await_args.kwargs["flow_id"] == UUID(flow_id_str)
        # Symmetric scope: the same coerced UUID is used for both calls.
        assert mock_store.await_args.kwargs["flow_id"] == mock_get.await_args.kwargs["flow_id"]

    @pytest.mark.asyncio
    async def test_store_does_not_crash_without_vertex(self):
        """When _vertex is None, ``self.graph`` raises AttributeError.

        Pre-fix, ``store_message`` accessed ``self.graph.flow_id`` directly
        and crashed before reaching the safe read path. Now both paths
        share the same defensive lookup.
        """
        component = MemoryComponent()
        component.set(
            session_id="s",
            n_messages=10,
            order="Ascending",
            mode="Store",
            message="hi",
            sender="User",
            sender_name="Tester",
        )
        # No _vertex assigned — ``self.graph`` will raise AttributeError.
        stored = SimpleNamespace(id="stored-1")
        with (
            patch(
                "lfx.components.models_and_agents.memory.astore_message",
                new=AsyncMock(return_value=None),
            ) as mock_store,
            patch(
                "lfx.components.models_and_agents.memory.aget_messages",
                new=AsyncMock(return_value=[stored]),
            ),
        ):
            await component.store_message()

        assert mock_store.await_args.kwargs["flow_id"] is None


class TestAgetAgentChatHistoryHelper:
    """The shared helper centralizes the agent-side memory contract.

    Both ``AgentComponent`` and ``CugaComponent`` route through this helper,
    so testing the helper directly covers their common behavior.
    """

    @pytest.mark.asyncio
    async def test_passes_flow_id_as_uuid(self):
        flow_id_str = "44444444-4444-4444-4444-444444444444"

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await aget_agent_chat_history(
                session_id="New Session 0",
                flow_id=flow_id_str,
                context_id="",
                n_messages=10,
            )

        mock_get.assert_awaited_once()
        kwargs = mock_get.await_args.kwargs
        assert kwargs["flow_id"] == UUID(flow_id_str), "aget_agent_chat_history must scope by flow_id (issue #13059)."
        assert kwargs["session_id"] == "New Session 0"
        # PR #13087 review I2: query DESC + limit=n_messages so sessions
        # exceeding MAX_CHAT_HISTORY_FETCH_LIMIT still get the real tail.
        assert kwargs["order"] == "DESC"
        assert kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_n_messages_zero_short_circuits_without_querying(self):
        """Regression: ``n_messages == 0`` means "memory disabled".

        Before this short-circuit, ``messages[-0:]`` returned the full
        bounded result, so users who set the field to 0 to disable chat
        memory unexpectedly got full history back.
        """
        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[SimpleNamespace(id=f"msg-{i}") for i in range(5)]),
        ) as mock_get:
            result = await aget_agent_chat_history(
                session_id="s",
                flow_id="66666666-6666-6666-6666-666666666666",
                n_messages=0,
            )

        assert result == []
        mock_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_slices_to_n_messages_most_recent(self):
        # DB returns DESC (most recent first); helper reverses to ASC.
        desc_rows = [SimpleNamespace(id=f"msg-{i}") for i in (4, 3)]

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=desc_rows),
        ) as mock_get:
            result = await aget_agent_chat_history(
                session_id="s",
                flow_id="77777777-7777-7777-7777-777777777777",
                n_messages=2,
            )

        assert mock_get.await_args.kwargs["limit"] == 2
        assert mock_get.await_args.kwargs["order"] == "DESC"
        assert [m.id for m in result] == ["msg-3", "msg-4"]

    @pytest.mark.asyncio
    async def test_missing_n_messages_returns_all_fetched(self):
        # DB returns DESC; helper reverses for the agent prompt.
        desc_rows = [SimpleNamespace(id=f"msg-{i}") for i in (2, 1, 0)]

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=desc_rows),
        ) as mock_get:
            result = await aget_agent_chat_history(
                session_id="s",
                flow_id=None,
                n_messages=None,
            )

        # No explicit limit ⇒ fall back to MAX_CHAT_HISTORY_FETCH_LIMIT.
        assert mock_get.await_args.kwargs["limit"] == MAX_CHAT_HISTORY_FETCH_LIMIT
        assert [m.id for m in result] == ["msg-0", "msg-1", "msg-2"]

    @pytest.mark.asyncio
    async def test_invalid_flow_id_falls_back_to_unscoped_query(self):
        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[]),
        ) as mock_get:
            await aget_agent_chat_history(
                session_id="s",
                flow_id="not-a-uuid",
                n_messages=10,
            )

        assert mock_get.await_args.kwargs["flow_id"] is None

    @pytest.mark.asyncio
    async def test_logs_warning_when_unbounded_fetch_hits_ceiling(self):
        """PR #13087 review I2: surface the silent-truncation case.

        When the caller did not pass ``n_messages`` and the DB returned
        exactly ``MAX_CHAT_HISTORY_FETCH_LIMIT`` rows, older history may
        have been silently dropped. Emit a structured warning so on-call
        has something to grep when a user reports forgotten context.
        """
        # Simulate the DB returning exactly the ceiling — older rows truncated.
        rows = [SimpleNamespace(id=f"msg-{i}") for i in range(MAX_CHAT_HISTORY_FETCH_LIMIT)]
        with (
            patch("lfx.components.models_and_agents.memory.logger") as mock_logger,
            patch(
                "lfx.components.models_and_agents.memory.aget_messages",
                new=AsyncMock(return_value=rows),
            ),
        ):
            await aget_agent_chat_history(
                session_id="s",
                flow_id=None,
                n_messages=None,
            )

        mock_logger.warning.assert_called_once()
        call = mock_logger.warning.call_args
        assert "memory_chat_history_limit_reached" in call.args[0]
        assert call.kwargs.get("extra", {}).get("event") == "memory_chat_history_limit_reached"

    @pytest.mark.asyncio
    async def test_explicit_n_messages_at_ceiling_does_not_warn(self):
        """The ceiling warning is for ``n_messages=None`` only — explicit limits are honored."""
        rows = [SimpleNamespace(id=f"msg-{i}") for i in range(MAX_CHAT_HISTORY_FETCH_LIMIT)]
        with (
            patch("lfx.components.models_and_agents.memory.logger") as mock_logger,
            patch(
                "lfx.components.models_and_agents.memory.aget_messages",
                new=AsyncMock(return_value=rows),
            ),
        ):
            await aget_agent_chat_history(
                session_id="s",
                flow_id=None,
                n_messages=MAX_CHAT_HISTORY_FETCH_LIMIT,
            )

        mock_logger.warning.assert_not_called()


class TestAgentGetMemoryDataIntegration:
    """End-to-end checks at the AgentComponent boundary."""

    @staticmethod
    def _make_agent(flow_id: str | UUID | None, session_id: str = "New Session 0", n_messages: int = 10):
        from lfx.components.models_and_agents.agent import AgentComponent

        agent = AgentComponent.__new__(AgentComponent)
        agent._vertex = SimpleNamespace(graph=SimpleNamespace(flow_id=flow_id, session_id=session_id))
        agent.context_id = ""
        agent.n_messages = n_messages
        agent.input_value = SimpleNamespace(id="current-input-id")
        return agent

    @pytest.mark.asyncio
    async def test_agent_routes_through_helper_with_flow_id(self):
        flow_id_str = "88888888-8888-8888-8888-888888888888"
        agent = self._make_agent(flow_id=flow_id_str)

        with patch(
            "lfx.components.models_and_agents.agent.aget_agent_chat_history",
            new=AsyncMock(return_value=[]),
        ) as mock_helper:
            await agent.get_memory_data()

        mock_helper.assert_awaited_once()
        kwargs = mock_helper.await_args.kwargs
        assert kwargs["flow_id"] == flow_id_str
        assert kwargs["session_id"] == "New Session 0"
        assert kwargs["n_messages"] == 10

    @pytest.mark.asyncio
    async def test_agent_filters_out_current_input_message(self):
        """The agent must not echo the current input back as chat history."""
        agent = self._make_agent(flow_id="55555555-5555-5555-5555-555555555555")

        current = SimpleNamespace(id="current-input-id", text="ping")
        old = SimpleNamespace(id="old-msg-id", text="earlier")

        with patch(
            "lfx.components.models_and_agents.agent.aget_agent_chat_history",
            new=AsyncMock(return_value=[old, current]),
        ):
            result = await agent.get_memory_data()

        assert [m.id for m in result] == ["old-msg-id"]

    @pytest.mark.asyncio
    async def test_agent_n_messages_zero_disables_memory(self):
        """Regression: setting "Number of Chat History Messages" to 0 must disable memory."""
        agent = self._make_agent(flow_id="99999999-9999-9999-9999-999999999999", n_messages=0)

        # Patch the underlying DB query so a regression resurfaces as a real call.
        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[SimpleNamespace(id=f"msg-{i}") for i in range(5)]),
        ) as mock_get:
            result = await agent.get_memory_data()

        assert result == []
        mock_get.assert_not_awaited()


class TestCugaGetMemoryDataIntegration:
    """The Cuga agent had the same leak pattern; verify the fix reaches it too."""

    @staticmethod
    def _make_cuga(flow_id: str | UUID | None, session_id: str = "shared", n_messages: int = 10):
        try:
            from lfx.components.cuga import cuga_agent
        except Exception as exc:  # pragma: no cover - optional deps
            pytest.skip(f"cuga_agent not importable in this env: {exc}")

        agent = cuga_agent.CugaComponent.__new__(cuga_agent.CugaComponent)
        agent._vertex = SimpleNamespace(graph=SimpleNamespace(flow_id=flow_id, session_id=session_id))
        agent.n_messages = n_messages
        agent.input_value = SimpleNamespace(id="current-input-id")
        return agent

    @pytest.mark.asyncio
    async def test_cuga_scopes_by_flow_id(self):
        flow_id_str = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        agent = self._make_cuga(flow_id=flow_id_str)

        with patch(
            "lfx.components.cuga.cuga_agent.aget_agent_chat_history",
            new=AsyncMock(return_value=[]),
        ) as mock_helper:
            await agent.get_memory_data()

        kwargs = mock_helper.await_args.kwargs
        assert kwargs["flow_id"] == flow_id_str
        assert kwargs["session_id"] == "shared"

    @pytest.mark.asyncio
    async def test_cuga_n_messages_zero_disables_memory(self):
        agent = self._make_cuga(flow_id="dddddddd-dddd-dddd-dddd-dddddddddddd", n_messages=0)

        with patch(
            "lfx.components.models_and_agents.memory.aget_messages",
            new=AsyncMock(return_value=[SimpleNamespace(id=f"msg-{i}") for i in range(3)]),
        ) as mock_get:
            result = await agent.get_memory_data()

        assert result == []
        mock_get.assert_not_awaited()
