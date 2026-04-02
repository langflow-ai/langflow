"""Tests for TokenUsageCallbackHandler wiring in LCAgentComponent.run_agent()."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_classic.agents import AgentExecutor
from langchain_core.runnables import Runnable
from lfx.base.agents.token_callback import TokenUsageCallbackHandler
from lfx.schema.message import Message
from lfx.schema.properties import Usage


def _make_vertex_stub():
    """Return a minimal vertex stub with a graph attribute."""
    return SimpleNamespace(graph=SimpleNamespace(session_id=None, flow_id=None, user_id=None))


async def _empty_astream():
    """Async generator that yields nothing — simulates an empty event stream."""
    return
    yield  # pragma: no cover — needed to make this an async generator


def _make_agent_executor_mock():
    """Create a minimal AgentExecutor mock with astream_events returning empty stream."""
    runnable = MagicMock(spec=AgentExecutor)
    runnable.astream_events.return_value = _empty_astream()
    return runnable


def _make_agent_component(agent_class, result_message):
    """Create a minimal concrete agent component stub for testing."""
    component = agent_class.__new__(agent_class)
    component._token_usage = None
    component._vertex = _make_vertex_stub()
    component._event_manager = None
    component.tools = []
    component.input_value = "test input"
    component.status = None
    component.chat_history = []
    component.send_message = AsyncMock(return_value=result_message)
    component._get_shared_callbacks = MagicMock(return_value=[])
    component.log = MagicMock()
    return component


class TestAgentTokenCallbackWiring:
    """Tests that TokenUsageCallbackHandler is properly wired into run_agent()."""

    @pytest.mark.asyncio
    async def test_token_usage_stored_on_component_when_handler_returns_usage(self):
        # Arrange
        from lfx.base.agents.agent import LCAgentComponent

        usage = Usage(input_tokens=50, output_tokens=30, total_tokens=80)
        result_message = Message(text="Agent response", id="msg-id")

        with (
            patch("lfx.base.agents.agent.TokenUsageCallbackHandler") as mock_handler_cls,
            patch("lfx.base.agents.agent.process_agent_events", new_callable=AsyncMock, return_value=result_message),
        ):
            handler_instance = MagicMock(spec=TokenUsageCallbackHandler)
            handler_instance.get_usage.return_value = usage
            mock_handler_cls.return_value = handler_instance

            class ConcreteAgent(LCAgentComponent):
                def create_agent_runnable(self) -> Runnable:
                    return MagicMock()

            agent_component = _make_agent_component(ConcreteAgent, result_message)
            agent_component._update_stored_message = AsyncMock(return_value=result_message)
            agent_component._send_message_event = AsyncMock()

            # Act
            await agent_component.run_agent(_make_agent_executor_mock())

        # Assert
        assert agent_component._token_usage == usage

    @pytest.mark.asyncio
    async def test_token_usage_not_set_when_handler_returns_none(self):
        # Arrange
        from lfx.base.agents.agent import LCAgentComponent

        result_message = Message(text="Agent response")

        with (
            patch("lfx.base.agents.agent.TokenUsageCallbackHandler") as mock_handler_cls,
            patch("lfx.base.agents.agent.process_agent_events", new_callable=AsyncMock, return_value=result_message),
        ):
            handler_instance = MagicMock(spec=TokenUsageCallbackHandler)
            handler_instance.get_usage.return_value = None
            mock_handler_cls.return_value = handler_instance

            class ConcreteAgent(LCAgentComponent):
                def create_agent_runnable(self) -> Runnable:
                    return MagicMock()

            agent_component = _make_agent_component(ConcreteAgent, result_message)

            # Act
            await agent_component.run_agent(_make_agent_executor_mock())

        # Assert: _token_usage should remain None
        assert agent_component._token_usage is None

    @pytest.mark.asyncio
    async def test_token_usage_handler_included_in_callbacks(self):
        # Arrange
        from lfx.base.agents.agent import LCAgentComponent

        result_message = Message(text="Agent response")
        captured_callbacks = []

        def capture_callbacks(*_args, config=None, **_kwargs):
            # side_effect must be a regular function; capture config and return async generator
            if config and "callbacks" in config:
                captured_callbacks.extend(config["callbacks"])
            return _empty_astream()

        with (
            patch("lfx.base.agents.agent.process_agent_events", new_callable=AsyncMock, return_value=result_message),
        ):

            class ConcreteAgent(LCAgentComponent):
                def create_agent_runnable(self) -> Runnable:
                    return MagicMock()

            agent_component = _make_agent_component(ConcreteAgent, result_message)

            runnable = MagicMock(spec=AgentExecutor)
            runnable.astream_events.side_effect = capture_callbacks

            # Act
            await agent_component.run_agent(runnable)

        # Assert: TokenUsageCallbackHandler is in the callbacks list
        assert any(isinstance(cb, TokenUsageCallbackHandler) for cb in captured_callbacks)
