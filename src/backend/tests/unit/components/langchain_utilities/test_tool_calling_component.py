import pytest

from langflow.components.langchain_utilities import ToolCallingAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestToolCallingAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ToolCallingAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "llm": "mock_language_model",
            "system_prompt": "You are a helpful assistant.",
            "chat_history": [],
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "ToolCallingAgent"},
            {"version": "1.1.0", "module": "agents", "file_name": "tool_calling_agent"},
        ]

    def test_create_agent_runnable(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent_runnable = component.create_agent_runnable()
        assert agent_runnable is not None
        assert hasattr(agent_runnable, "run"), "Agent runnable should have a run method."

    def test_get_chat_history_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        chat_history_data = component.get_chat_history_data()
        assert chat_history_data == default_kwargs["chat_history"], "Chat history data should match the input."

    async def test_to_toolkit(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = await component.to_toolkit()
        assert isinstance(toolkit, list), "Toolkit should be a list."
        assert all(isinstance(tool, Tool) for tool in toolkit), "All items in toolkit should be of type Tool."
