import pytest

from langflow.components.cohere import CohereRerankComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCohereRerankComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CohereRerankComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "search_query": "What is the capital of France?",
            "model": "rerank-english-v3.0",
            "api_key": "test_api_key",
            "top_n": 3,
            "user_agent": "langflow",
            "retriever": "mock_retriever",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "retrievers", "file_name": "CohereRerank"},
        ]

    async def test_build_base_retriever(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        retriever = component.build_base_retriever()
        assert retriever is not None
        assert hasattr(retriever, "ainvoke")

    async def test_search_documents(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.search_documents()
        assert isinstance(result, list)
        assert len(result) <= default_kwargs["top_n"]

    def test_vector_store_not_supported(self, component_class):
        component = component_class()
        with pytest.raises(NotImplementedError, match="Cohere Rerank does not support vector stores."):
            component.build_vector_store()
