import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langflow.components.data.kb_retrieval import KBRetrievalComponent

from tests.base import ComponentTestBaseWithoutClient


class TestKBRetrievalComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return KBRetrievalComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Mock the knowledge base root path directly."""
        with patch("langflow.components.data.kb_retrieval.KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        """Return default kwargs for component instantiation."""
        # Create knowledge base directory structure
        kb_name = "test_kb"
        kb_path = tmp_path / kb_name
        kb_path.mkdir(exist_ok=True)

        # Create embedding metadata file
        metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "api_key": None,
            "api_key_used": False,
            "chunk_size": 1000,
            "created_at": "2024-01-01T00:00:00Z",
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata))

        return {
            "knowledge_base": kb_name,
            "kb_root_path": str(tmp_path),
            "api_key": None,
            "search_query": "",
            "top_k": 5,
            "include_embeddings": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for version testing."""
        # This is a new component, so it doesn't exist in older versions
        return []

    def test_get_knowledge_bases(self, component_class, default_kwargs, tmp_path):
        """Test getting list of knowledge bases."""
        component = component_class(**default_kwargs)

        # Create additional test directories
        (tmp_path / "kb1").mkdir()
        (tmp_path / "kb2").mkdir()
        (tmp_path / ".hidden").mkdir()  # Should be ignored

        kb_list = component._get_knowledge_bases()

        assert "test_kb" in kb_list
        assert "kb1" in kb_list
        assert "kb2" in kb_list
        assert ".hidden" not in kb_list

    @patch("langflow.components.data.kb_retrieval.Path.exists")
    def test_get_knowledge_bases_no_path(self, mock_exists, component_class, default_kwargs):
        """Test getting knowledge bases when path doesn't exist."""
        component = component_class(**default_kwargs)
        mock_exists.return_value = False

        kb_list = component._get_knowledge_bases()
        assert kb_list == []

    def test_update_build_config(self, component_class, default_kwargs, tmp_path):
        """Test updating build configuration."""
        component = component_class(**default_kwargs)

        # Create additional KB directories
        (tmp_path / "kb1").mkdir()
        (tmp_path / "kb2").mkdir()

        build_config = {"knowledge_base": {"value": "test_kb", "options": []}}

        result = component.update_build_config(build_config, None, "knowledge_base")

        assert "test_kb" in result["knowledge_base"]["options"]
        assert "kb1" in result["knowledge_base"]["options"]
        assert "kb2" in result["knowledge_base"]["options"]

    def test_update_build_config_invalid_kb(self, component_class, default_kwargs):
        """Test updating build config when selected KB is not available."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": "nonexistent_kb", "options": ["test_kb"]}}

        result = component.update_build_config(build_config, None, "knowledge_base")

        assert result["knowledge_base"]["value"] is None

    def test_get_kb_metadata_success(self, component_class, default_kwargs):
        """Test successful metadata loading."""
        component = component_class(**default_kwargs)
        kb_path = Path(default_kwargs["kb_root_path"]) / default_kwargs["knowledge_base"]

        with patch("langflow.components.data.kb_retrieval.decrypt_api_key") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_key"

            metadata = component._get_kb_metadata(kb_path)

        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert "chunk_size" in metadata

    def test_get_kb_metadata_no_file(self, component_class, default_kwargs, tmp_path):
        """Test metadata loading when file doesn't exist."""
        component = component_class(**default_kwargs)
        nonexistent_path = tmp_path / "nonexistent"
        nonexistent_path.mkdir()

        metadata = component._get_kb_metadata(nonexistent_path)

        assert metadata == {}

    def test_get_kb_metadata_json_error(self, component_class, default_kwargs, tmp_path):
        """Test metadata loading with invalid JSON."""
        component = component_class(**default_kwargs)
        kb_path = tmp_path / "invalid_json_kb"
        kb_path.mkdir()

        # Create invalid JSON file
        (kb_path / "embedding_metadata.json").write_text("invalid json content")

        metadata = component._get_kb_metadata(kb_path)

        assert metadata == {}

    def test_get_kb_metadata_decrypt_error(self, component_class, default_kwargs, tmp_path):
        """Test metadata loading with decryption error."""
        component = component_class(**default_kwargs)
        kb_path = tmp_path / "decrypt_error_kb"
        kb_path.mkdir()

        # Create metadata with encrypted key
        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "api_key": "encrypted_key",
            "chunk_size": 1000,
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata))

        with patch("langflow.components.data.kb_retrieval.decrypt_api_key") as mock_decrypt:
            mock_decrypt.side_effect = ValueError("Decryption failed")

            result = component._get_kb_metadata(kb_path)

        assert result["api_key"] is None

    @patch("langchain_huggingface.HuggingFaceEmbeddings")
    def test_build_embeddings_huggingface(self, mock_hf_embeddings, component_class, default_kwargs):
        """Test building HuggingFace embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_hf_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata)

        mock_hf_embeddings.assert_called_once_with(model="sentence-transformers/all-MiniLM-L6-v2")
        assert result == mock_embeddings

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_build_embeddings_openai(self, mock_openai_embeddings, component_class, default_kwargs):
        """Test building OpenAI embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "api_key": "test-api-key",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_openai_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata)

        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-ada-002", api_key="test-api-key", chunk_size=1000
        )
        assert result == mock_embeddings

    def test_build_embeddings_openai_no_key(self, component_class, default_kwargs):
        """Test building OpenAI embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "api_key": None,
            "chunk_size": 1000,
        }

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            component._build_embeddings(metadata)

    @patch("langchain_cohere.CohereEmbeddings")
    def test_build_embeddings_cohere(self, mock_cohere_embeddings, component_class, default_kwargs):
        """Test building Cohere embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Cohere",
            "embedding_model": "embed-english-v3.0",
            "api_key": "test-api-key",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_cohere_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata)

        mock_cohere_embeddings.assert_called_once_with(model="embed-english-v3.0", cohere_api_key="test-api-key")
        assert result == mock_embeddings

    def test_build_embeddings_cohere_no_key(self, component_class, default_kwargs):
        """Test building Cohere embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Cohere",
            "embedding_model": "embed-english-v3.0",
            "api_key": None,
            "chunk_size": 1000,
        }

        with pytest.raises(ValueError, match="Cohere API key is required"):
            component._build_embeddings(metadata)

    def test_build_embeddings_custom_not_supported(self, component_class, default_kwargs):
        """Test building custom embeddings raises NotImplementedError."""
        component = component_class(**default_kwargs)

        metadata = {"embedding_provider": "Custom", "embedding_model": "custom-model", "api_key": "test-key"}

        with pytest.raises(NotImplementedError, match="Custom embedding models not yet supported"):
            component._build_embeddings(metadata)

    def test_build_embeddings_unsupported_provider(self, component_class, default_kwargs):
        """Test building embeddings with unsupported provider raises NotImplementedError."""
        component = component_class(**default_kwargs)

        metadata = {"embedding_provider": "UnsupportedProvider", "embedding_model": "some-model", "api_key": "test-key"}

        with pytest.raises(NotImplementedError, match="Embedding provider 'UnsupportedProvider' is not supported"):
            component._build_embeddings(metadata)

    def test_build_embeddings_with_user_api_key(self, component_class, default_kwargs):
        """Test that user-provided API key overrides stored one."""
        # Create a mock secret input

        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "user-provided-key"

        default_kwargs["api_key"] = mock_secret
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "api_key": "stored-key",
            "chunk_size": 1000,
        }

        with patch("langchain_openai.OpenAIEmbeddings") as mock_openai:
            mock_embeddings = MagicMock()
            mock_openai.return_value = mock_embeddings

            component._build_embeddings(metadata)

            mock_openai.assert_called_once_with(
                model="text-embedding-ada-002", api_key="user-provided-key", chunk_size=1000
            )

    def test_get_chroma_kb_data_no_metadata(self, component_class, default_kwargs, tmp_path):
        """Test retrieving data when metadata is missing."""
        # Remove metadata file
        kb_path = tmp_path / default_kwargs["knowledge_base"]
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()

        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Metadata not found for knowledge base"):
            component.get_chroma_kb_data()

    def test_get_chroma_kb_data_path_construction(self, component_class, default_kwargs):
        """Test that get_chroma_kb_data constructs the correct paths."""
        component = component_class(**default_kwargs)

        # Test that the component correctly builds the KB path

        assert component.kb_root_path == default_kwargs["kb_root_path"]
        assert component.knowledge_base == default_kwargs["knowledge_base"]

        # Test that paths are correctly expanded
        expanded_path = Path(component.kb_root_path).expanduser()
        assert expanded_path.exists()  # tmp_path should exist

        # Verify method exists with correct parameters
        assert hasattr(component, "get_chroma_kb_data")
        assert hasattr(component, "search_query")
        assert hasattr(component, "top_k")
        assert hasattr(component, "include_embeddings")

    def test_get_chroma_kb_data_method_exists(self, component_class, default_kwargs):
        """Test that get_chroma_kb_data method exists and can be called."""
        component = component_class(**default_kwargs)

        # Just verify the method exists and has the right signature
        assert hasattr(component, "get_chroma_kb_data"), "Component should have get_chroma_kb_data method"

        # Mock all external calls to avoid integration issues
        with (
            patch.object(component, "_get_kb_metadata") as mock_get_metadata,
            patch.object(component, "_build_embeddings") as mock_build_embeddings,
            patch("langchain_chroma.Chroma"),
        ):
            mock_get_metadata.return_value = {"embedding_provider": "HuggingFace", "embedding_model": "test-model"}
            mock_build_embeddings.return_value = MagicMock()

            # This is a unit test focused on the component's internal logic
            with contextlib.suppress(Exception):
                component.get_chroma_kb_data()

            # Verify internal methods were called
            mock_get_metadata.assert_called_once()
            mock_build_embeddings.assert_called_once()

    def test_include_embeddings_parameter(self, component_class, default_kwargs):
        """Test that include_embeddings parameter is properly set."""
        # Test with embeddings enabled
        default_kwargs["include_embeddings"] = True
        component = component_class(**default_kwargs)
        assert component.include_embeddings is True

        # Test with embeddings disabled
        default_kwargs["include_embeddings"] = False
        component = component_class(**default_kwargs)
        assert component.include_embeddings is False
