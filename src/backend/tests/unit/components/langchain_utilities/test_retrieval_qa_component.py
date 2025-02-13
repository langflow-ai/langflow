import pytest

from langflow.components.langchain_utilities import RetrievalQAComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRetrievalQAComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RetrievalQAComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "What is the capital of France?",
            "chain_type": "Stuff",
            "llm": "mock_llm",
            "retriever": "mock_retriever",
            "memory": None,
            "return_source_documents": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_invoke_chain(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.invoke_chain()
        assert result is not None
        assert isinstance(result, str)

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.input_value == "What is the capital of France?"
        assert component.chain_type == "Stuff"
        assert component.llm == "mock_llm"
        assert component.retriever == "mock_retriever"
        assert component.memory is None
        assert component.return_source_documents is False
