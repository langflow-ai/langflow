import pytest
from langflow.components.vectorstores import VectaraVectorStoreComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectaraVectorStoreComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectaraVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "vectara_customer_id": "customer_id_123",
            "vectara_corpus_id": "corpus_id_123",
            "vectara_api_key": "api_key_123",
            "number_of_results": 4,
            "ingest_data": [],
            "search_query": "example query",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstores", "file_name": "VectaraVectorStoreComponent"},
        ]

    async def test_build_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        vector_store = await component.build_vector_store()
        assert vector_store is not None
        assert hasattr(vector_store, "vectara_customer_id")
        assert vector_store.vectara_customer_id == default_kwargs["vectara_customer_id"]

    async def test_add_documents_to_vector_store(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = ["doc1", "doc2"]
        component._add_documents_to_vector_store(await component.build_vector_store())
        assert component.status == "Added 2 documents to Vectara"

    async def test_search_documents_with_results(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.ingest_data = ["doc1", "doc2"]
        await component.build_vector_store()
        results = await component.search_documents()
        assert isinstance(results, list)
        assert component.status.startswith("Found")

    async def test_search_documents_without_query(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.search_query = ""
        results = await component.search_documents()
        assert results == []
        assert component.status == "No search query provided"
