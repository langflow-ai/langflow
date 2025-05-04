import pytest
from langflow.components.langchain_utilities import ConversationChainComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestConversationChainComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ConversationChainComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, how are you?",
            "llm": "mock_llm",
            "memory": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "chains", "file_name": "ConversationChain"},
        ]

    async def test_invoke_chain_without_memory(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert isinstance(result, Message)
        assert result.text == "mock_response"  # Assuming mock response from the LLM

    async def test_invoke_chain_with_memory(self, component_class, default_kwargs):
        default_kwargs["memory"] = "mock_memory"
        component = component_class(**default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert isinstance(result, Message)
        assert result.text == "mock_response"  # Assuming mock response from the LLM
