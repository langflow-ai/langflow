import pytest
from langflow.components.langchain_utilities import XMLAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestXMLAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return XMLAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "llm": "mock_llm",
            "chat_history": [],
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "{input}",
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_create_agent_runnable_valid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        runnable = component.create_agent_runnable()
        assert runnable is not None

    def test_create_agent_runnable_missing_input_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.user_prompt = "This prompt does not contain the required key."
        with pytest.raises(ValueError, match="Prompt must contain 'input' key."):
            component.create_agent_runnable()

    def test_get_chat_history_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        chat_history_data = component.get_chat_history_data()
        assert chat_history_data == []
