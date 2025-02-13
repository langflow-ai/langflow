import pytest

from langflow.components.langchain_utilities import LLMMathChainComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLLMMathChainComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LLMMathChainComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "2 + 2",
            "llm": "mock_language_model",  # Mock or actual language model instance
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "math_chain", "file_name": "LLMMathChain"},
            {"version": "1.1.0", "module": "math_chain", "file_name": "llm_math_chain"},
        ]

    async def test_invoke_chain(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.invoke_chain()
        assert result.text == "4", "Expected result for '2 + 2' should be '4'."

    async def test_component_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
