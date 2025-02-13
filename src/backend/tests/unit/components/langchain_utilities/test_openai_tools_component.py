import pytest

from langflow.components.langchain_utilities import OpenAIToolsAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenAIToolsAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenAIToolsAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "llm": "mock_llm",
            "system_prompt": "You are a helpful assistant",
            "user_prompt": "{input}",
            "chat_history": [],
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "OpenAIToolsAgent"},
        ]

    def test_create_agent_runnable_with_valid_prompt(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent_runnable = component.create_agent_runnable()
        assert agent_runnable is not None

    def test_create_agent_runnable_without_input_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.user_prompt = "This prompt does not contain the key."
        with pytest.raises(ValueError, match="Prompt must contain 'input' key."):
            component.create_agent_runnable()

    def test_get_chat_history_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        chat_history_data = component.get_chat_history_data()
        assert chat_history_data == []
