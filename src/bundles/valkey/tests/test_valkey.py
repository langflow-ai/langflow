"""Unit tests for ValkeyVectorStoreComponent."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.vectorstores.model import LCVectorStoreComponent
from lfx.io import HandleInput, IntInput, SecretStrInput, StrInput
from lfx_valkey.components.valkey.valkey import ValkeyVectorStoreComponent

# Create a mock for langchain_aws.vectorstores
_mock_aws_module = ModuleType("langchain_aws")
_mock_vectorstores_module = ModuleType("langchain_aws.vectorstores")
_MockValkeyVectorStore = MagicMock()
_mock_vectorstores_module.ValkeyVectorStore = _MockValkeyVectorStore
_mock_aws_module.vectorstores = _mock_vectorstores_module


@pytest.fixture(autouse=True)
def _mock_langchain_aws():
    """Mock langchain_aws so tests work without it installed."""
    modules = {
        "langchain_aws": _mock_aws_module,
        "langchain_aws.vectorstores": _mock_vectorstores_module,
    }
    with patch.dict(sys.modules, modules):
        yield
    _MockValkeyVectorStore.reset_mock()


class TestValkeyVectorStoreComponentMetadata:
    def test_display_name(self):
        assert ValkeyVectorStoreComponent.display_name == "Valkey"

    def test_icon(self):
        assert ValkeyVectorStoreComponent.icon == "Valkey"

    def test_name(self):
        assert ValkeyVectorStoreComponent.name == "Valkey"

    def test_description(self):
        assert ValkeyVectorStoreComponent.description == "Implementation of Vector Store using Valkey"


class TestValkeyVectorStoreComponentInheritance:
    def test_inherits_from_lc_vector_store_component(self):
        assert issubclass(ValkeyVectorStoreComponent, LCVectorStoreComponent)


class TestValkeyVectorStoreComponentInputs:
    def _get_input(self, name: str):
        for inp in ValkeyVectorStoreComponent.inputs:
            if inp.name == name:
                return inp
        msg = f"Input '{name}' not found"
        raise AssertionError(msg)

    def test_valkey_server_url_input(self):
        inp = self._get_input("valkey_server_url")
        assert isinstance(inp, SecretStrInput)
        assert inp.required is True

    def test_valkey_index_name_input(self):
        inp = self._get_input("valkey_index_name")
        assert isinstance(inp, StrInput)

    def test_number_of_results_input(self):
        inp = self._get_input("number_of_results")
        assert isinstance(inp, IntInput)
        assert inp.value == 4
        assert inp.advanced is True

    def test_embedding_input(self):
        inp = self._get_input("embedding")
        assert isinstance(inp, HandleInput)
        assert "Embeddings" in inp.input_types

    def test_inherited_inputs_present(self):
        input_names = [inp.name for inp in ValkeyVectorStoreComponent.inputs]
        assert "search_query" in input_names
        assert "ingest_data" in input_names

    def test_all_expected_input_names(self):
        input_names = [inp.name for inp in ValkeyVectorStoreComponent.inputs]
        assert "valkey_server_url" in input_names
        assert "valkey_index_name" in input_names
        assert "number_of_results" in input_names
        assert "embedding" in input_names


class TestValkeyVectorStoreComponentDecorator:
    def test_build_vector_store_has_cached_decorator(self):
        assert hasattr(ValkeyVectorStoreComponent.build_vector_store, "is_cached_vector_store_checked")


class TestValkeyVectorStoreComponentBehavior:
    def test_no_data_no_index_raises_value_error(self):
        component = ValkeyVectorStoreComponent()
        component.ingest_data = []
        component.valkey_index_name = ""
        component.valkey_server_url = "valkey://localhost:6379"
        component.embedding = MagicMock()
        component._should_cache_vector_store = False
        with pytest.raises(ValueError, match="index name must be provided"):
            component.build_vector_store()

    def test_no_data_none_index_raises_value_error(self):
        component = ValkeyVectorStoreComponent()
        component.ingest_data = []
        component.valkey_index_name = None
        component.valkey_server_url = "valkey://localhost:6379"
        component.embedding = MagicMock()
        component._should_cache_vector_store = False
        with pytest.raises(ValueError, match="index name must be provided"):
            component.build_vector_store()

    def test_no_data_with_index_calls_from_existing_index(self):
        component = ValkeyVectorStoreComponent()
        component.ingest_data = []
        component.valkey_index_name = "my_index"
        component.valkey_server_url = "valkey://localhost:6379"
        component.embedding = MagicMock()
        component._should_cache_vector_store = False
        component.build_vector_store()
        _MockValkeyVectorStore.from_existing_index.assert_called_once_with(
            embedding=component.embedding,
            valkey_url="valkey://localhost:6379",
            index_name="my_index",
        )

    def test_with_documents_calls_from_documents(self):
        from lfx.schema.data import Data

        component = ValkeyVectorStoreComponent()
        mock_data = MagicMock(spec=Data)
        mock_doc = MagicMock()
        mock_data.to_lc_document.return_value = mock_doc
        component.ingest_data = [mock_data]
        component.valkey_index_name = "my_index"
        component.valkey_server_url = "valkey://localhost:6379"
        component.embedding = MagicMock()
        component._should_cache_vector_store = False
        component.build_vector_store()
        _MockValkeyVectorStore.from_documents.assert_called_once_with(
            documents=[mock_doc],
            embedding=component.embedding,
            valkey_url="valkey://localhost:6379",
            index_name="my_index",
        )

    def test_empty_search_query_returns_empty_list(self):
        component = ValkeyVectorStoreComponent()
        component.search_query = ""
        component.number_of_results = 4
        component.build_vector_store = MagicMock()
        result = component.search_documents()
        assert result == []

    def test_blank_search_query_returns_empty_list(self):
        component = ValkeyVectorStoreComponent()
        component.search_query = "   "
        component.number_of_results = 4
        component.build_vector_store = MagicMock()
        result = component.search_documents()
        assert result == []

    def test_none_search_query_returns_empty_list(self):
        component = ValkeyVectorStoreComponent()
        component.search_query = None
        component.number_of_results = 4
        component.build_vector_store = MagicMock()
        result = component.search_documents()
        assert result == []
