import pytest

from langflow.components.langchain_utilities import SelfQueryRetrieverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSelfQueryRetrieverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SelfQueryRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "query": "What is the capital of France?",
            "vectorstore": "mock_vectorstore",
            "attribute_infos": [{"data": {"field": "value"}}],
            "document_content_description": "Description of the document content.",
            "llm": "mock_llm",
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "retrievers", "file_name": "SelfQueryRetriever"},
        ]

    async def test_retrieve_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.retrieve_documents()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(doc, Data) for doc in result)

    async def test_invalid_query_type(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.query = 123  # Invalid query type
        with pytest.raises(TypeError, match="Query type <class 'int'> not supported."):
            await component.retrieve_documents()
