"""Shared fixtures for execution tests."""

from __future__ import annotations

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.execution import reset_default_coordinator
from lfx.graph import Graph


@pytest.fixture(autouse=True)
def _reset_execution_singletons():
    reset_default_coordinator()
    yield
    reset_default_coordinator()


@pytest.fixture
def simple_graph():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    return Graph(chat_input, chat_output)
