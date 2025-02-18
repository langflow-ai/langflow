import pytest
from langflow.components.vectorstores import VectaraRagComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectaraRagComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectaraRagComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "vectara_customer_id": "customer_id_123",
            "vectara_corpus_id": "corpus_id_123",
            "vectara_api_key": "api_key_123",
            "search_query": "What is the capital of France?",
            "reranker": "mmr",
            "reranker_k": 50,
            "diversity_bias": 0.2,
            "max_results": 7,
            "response_lang": "eng",
            "prompt": "vectara-summary-ext-24-05-sml",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectara_rag", "file_name": "VectaraRag"},
        ]

    async def test_generate_response(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.generate_response()
        assert result is not None
        assert isinstance(result.text, str)
        assert len(result.text) > 0

    async def test_component_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None
