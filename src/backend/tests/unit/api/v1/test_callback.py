from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.agents import AgentAction, AgentFinish
from langflow.api.v1.callback import AsyncStreamingLLMCallbackHandleSIO
from langflow.api.v1.schemas import ChatResponse, PromptResponse


class TestAsyncStreamingLLMCallbackHandleSIO:
    """Test cases for AsyncStreamingLLMCallbackHandleSIO callback handler."""

    @pytest.fixture
    def session_id(self):
        return str(uuid4())

    @pytest.fixture
    def mock_chat_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_socket_service(self):
        mock_service = MagicMock()
        mock_service.emit_token = AsyncMock()
        mock_service.emit_message = AsyncMock()
        return mock_service

    @pytest.fixture
    def callback_handler(self, session_id, mock_chat_service, mock_socket_service):
        with (
            patch("langflow.api.v1.callback.get_chat_service", return_value=mock_chat_service),
            patch("langflow.api.v1.callback.get_socket_service", return_value=mock_socket_service),
        ):
            return AsyncStreamingLLMCallbackHandleSIO(session_id)

    def test_ignore_chain_property(self, callback_handler):
        """Test that ignore_chain property returns False."""
        assert callback_handler.ignore_chain is False

    def test_initialization(self, session_id, mock_chat_service, mock_socket_service):
        """Test proper initialization of callback handler."""
        with (
            patch("langflow.api.v1.callback.get_chat_service", return_value=mock_chat_service),
            patch("langflow.api.v1.callback.get_socket_service", return_value=mock_socket_service),
        ):
            handler = AsyncStreamingLLMCallbackHandleSIO(session_id)

            assert handler.client_id == session_id
            assert handler.sid == session_id
            assert handler.chat_service == mock_chat_service
            assert handler.socketio_service == mock_socket_service

    @pytest.mark.asyncio
    async def test_on_llm_new_token(self, callback_handler):
        """Test on_llm_new_token method."""
        token = "test_token"  # noqa: S105

        await callback_handler.on_llm_new_token(token)

        expected_response = ChatResponse(message=token, type="stream", intermediate_steps="")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )

    @pytest.mark.asyncio
    async def test_on_tool_start(self, callback_handler):
        """Test on_tool_start method."""
        serialized = {"name": "test_tool"}
        input_str = "test input"

        await callback_handler.on_tool_start(serialized, input_str)

        expected_response = ChatResponse(message="", type="stream", intermediate_steps=f"Tool input: {input_str}")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )

    @pytest.mark.asyncio
    async def test_on_tool_end_single_word(self, callback_handler):
        """Test on_tool_end method with single word output."""
        output = "result"

        await callback_handler.on_tool_end(output)

        expected_response = ChatResponse(message="", type="stream", intermediate_steps="Tool output: result")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )

    @pytest.mark.asyncio
    async def test_on_tool_end_multiple_words(self, callback_handler):
        """Test on_tool_end method with multiple words output."""
        output = "result with multiple words"

        await callback_handler.on_tool_end(output)

        # Should be called 4 times (one for first word + prefix, then 3 more for remaining words)
        assert callback_handler.socketio_service.emit_token.call_count == 4

    @pytest.mark.asyncio
    async def test_on_tool_end_with_custom_observation_prefix(self, callback_handler):
        """Test on_tool_end method with custom observation prefix."""
        output = "result"
        observation_prefix = "Custom prefix: "

        await callback_handler.on_tool_end(output, observation_prefix=observation_prefix)

        expected_response = ChatResponse(message="", type="stream", intermediate_steps="Custom prefix: result")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )

    @pytest.mark.asyncio
    async def test_on_tool_end_exception_handling(self, callback_handler):
        """Test on_tool_end method handles exceptions gracefully."""
        callback_handler.socketio_service.emit_token.side_effect = Exception("Socket error")
        output = "result"

        # Should not raise exception
        await callback_handler.on_tool_end(output)

    @pytest.mark.asyncio
    async def test_on_tool_error(self, callback_handler):
        """Test on_tool_error method."""
        error = Exception("Test error")
        run_id = uuid4()
        parent_run_id = uuid4()
        tags = ["tag1", "tag2"]

        # Should not raise exception (method is empty)
        await callback_handler.on_tool_error(error, run_id=run_id, parent_run_id=parent_run_id, tags=tags)

    @pytest.mark.asyncio
    async def test_on_text_with_prompt_formatting(self, callback_handler):
        """Test on_text method with prompt formatting text."""
        text = "Prompt after formatting:\nActual prompt content"

        with patch(
            "langflow.api.v1.callback.remove_ansi_escape_codes", return_value="Actual prompt content"
        ) as mock_remove:
            await callback_handler.on_text(text)

            mock_remove.assert_called_once_with("Actual prompt content")
            expected_response = PromptResponse(prompt="Actual prompt content")
            callback_handler.socketio_service.emit_message.assert_called_once_with(
                to=callback_handler.sid, data=expected_response.model_dump()
            )

    @pytest.mark.asyncio
    async def test_on_text_without_prompt_formatting(self, callback_handler):
        """Test on_text method without prompt formatting text."""
        text = "Regular text content"

        await callback_handler.on_text(text)

        # Should not emit any message
        callback_handler.socketio_service.emit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_agent_action_single_line(self, callback_handler):
        """Test on_agent_action method with single line log."""
        action = AgentAction(tool="test_tool", tool_input="input", log="Single line thought")

        await callback_handler.on_agent_action(action)

        expected_response = ChatResponse(message="", type="stream", intermediate_steps="Thought: Single line thought")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )

    @pytest.mark.asyncio
    async def test_on_agent_action_multiple_lines(self, callback_handler):
        """Test on_agent_action method with multiple line log."""
        action = AgentAction(tool="test_tool", tool_input="input", log="First line\nSecond line\nThird line")

        await callback_handler.on_agent_action(action)

        # Should be called 3 times (once for each line)
        assert callback_handler.socketio_service.emit_token.call_count == 3

    @pytest.mark.asyncio
    async def test_on_agent_finish(self, callback_handler):
        """Test on_agent_finish method."""
        finish = AgentFinish(return_values={"output": "result"}, log="Agent finished")

        await callback_handler.on_agent_finish(finish)

        expected_response = ChatResponse(message="", type="stream", intermediate_steps="Agent finished")
        callback_handler.socketio_service.emit_token.assert_called_once_with(
            to=callback_handler.sid, data=expected_response.model_dump()
        )
