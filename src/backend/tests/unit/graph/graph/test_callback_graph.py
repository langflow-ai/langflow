import asyncio

import pytest
from langflow.custom import Component
from langflow.events.event_manager import EventManager
from langflow.inputs import IntInput
from langflow.schema.message import Message
from langflow.template import Output

from lfx.components.input_output import ChatOutput
from lfx.graph import Graph


class LogComponent(Component):
    display_name = "LogComponent"
    inputs = [IntInput(name="times", value=1)]
    outputs = [Output(name="call_log", method="call_log_method")]

    def call_log_method(self) -> Message:
        for i in range(self.times):
            self.log(f"This is log message {i}", name=f"Log {i}")
        return Message(text="Log called", sender="test_sender", sender_name="test_sender_name")


@pytest.mark.skip(reason="Temporarily disabled")
def test_callback_graph():
    logs: list[tuple[str, dict]] = []

    def mock_callback(manager, event_type: str, data: dict):  # noqa: ARG001
        logs.append((event_type, data))

    event_manager = EventManager(queue=asyncio.Queue())
    event_manager.register_event("on_log", "log", callback=mock_callback)

    log_component = LogComponent(_id="log_component")
    log_component.set(times=3)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(
        input_value="test_input_value", sender_name=log_component.call_log_method, session_id="test_session_id"
    )
    graph = Graph(start=log_component, end=chat_output)
    graph.session_id = "test_session_id"
    results = list(graph.start(event_manager=event_manager))
    assert len(results) == 3
    assert len(logs) == 3
    assert all(isinstance(log, tuple) for log in logs)
    assert all(isinstance(log[1], dict) for log in logs)
    assert logs[0][0] == "log"
    assert logs[0][1]["name"] == "Log 0"
    assert logs[1][0] == "log"
    assert logs[1][1]["name"] == "Log 1"
    assert logs[2][0] == "log"
    assert logs[2][1]["name"] == "Log 2"
