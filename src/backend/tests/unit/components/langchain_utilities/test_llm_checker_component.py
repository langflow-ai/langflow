import pytest
from langflow.components.langchain_utilities import LLMCheckerChainComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLLMCheckerChainComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LLMCheckerChainComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "What is the capital of France?",
            "llm": "mock_language_model",  # Mock or actual LLM instance as needed
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "llm_checker", "file_name": "LLMCheckerChain"},
        ]

    async def test_invoke_chain(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert isinstance(result, Message)
        assert result.text != "", "The result text should not be empty."

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None
