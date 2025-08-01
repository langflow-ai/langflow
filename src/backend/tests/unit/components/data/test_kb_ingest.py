import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from langflow.components.data.kb_ingest import KBIngestionComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestKBIngestionComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return KBIngestionComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Mock the knowledge base root path directly."""
        with patch("langflow.components.data.kb_ingest.KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        """Return default kwargs for component instantiation."""
        # Create a sample DataFrame
        data_df = pd.DataFrame(
            {"text": ["Sample text 1", "Sample text 2"], "title": ["Title 1", "Title 2"], "category": ["cat1", "cat2"]}
        )

        # Create column configuration
        column_config = [
            {"column_name": "text", "vectorize": True, "identifier": False},
            {"column_name": "title", "vectorize": False, "identifier": False},
            {"column_name": "category", "vectorize": False, "identifier": True},
        ]

        # Create knowledge base directory
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
            "input_df": data_df,
            "column_config": column_config,
            "chunk_size": 1000,
            "kb_root_path": str(tmp_path),
            "api_key": None,
            "allow_duplicates": False,
            "silent_errors": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for version testing."""
        # This is a new component, so it doesn't exist in older versions
        return []

    def test_validate_column_config_valid(self, component_class, default_kwargs):
        """Test column configuration validation with valid config."""
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]

        config_list = component._validate_column_config(data_df)

        assert len(config_list) == 3
        assert config_list[0]["column_name"] == "text"
        assert config_list[0]["vectorize"] is True

    def test_validate_column_config_invalid_column(self, component_class, default_kwargs):
        """Test column configuration validation with invalid column name."""
        # Modify column config to include non-existent column
        invalid_config = [{"column_name": "nonexistent", "vectorize": True, "identifier": False}]
        default_kwargs["column_config"] = invalid_config

        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]

        with pytest.raises(ValueError, match="Column 'nonexistent' not found in DataFrame"):
            component._validate_column_config(data_df)

    def test_validate_column_config_silent_errors(self, component_class, default_kwargs):
        """Test column configuration validation with silent errors enabled."""
        # Modify column config to include non-existent column
        invalid_config = [{"column_name": "nonexistent", "vectorize": True, "identifier": False}]
        default_kwargs["column_config"] = invalid_config
        default_kwargs["silent_errors"] = True

        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]

        # Should not raise exception with silent_errors=True
        config_list = component._validate_column_config(data_df)
        assert isinstance(config_list, list)

    def test_get_embedding_provider(self, component_class, default_kwargs):
        """Test embedding provider detection."""
        component = component_class(**default_kwargs)

        # Test OpenAI provider
        assert component._get_embedding_provider("text-embedding-ada-002") == "OpenAI"

        # Test HuggingFace provider
        assert component._get_embedding_provider("sentence-transformers/all-MiniLM-L6-v2") == "HuggingFace"

        # Test Cohere provider
        assert component._get_embedding_provider("embed-english-v3.0") == "Cohere"

        # Test custom provider
        assert component._get_embedding_provider("custom-model") == "Custom"

    @patch("langchain_huggingface.HuggingFaceEmbeddings")
    def test_build_embeddings_huggingface(self, mock_hf_embeddings, component_class, default_kwargs):
        """Test building HuggingFace embeddings."""
        component = component_class(**default_kwargs)

        mock_embeddings = MagicMock()
        mock_hf_embeddings.return_value = mock_embeddings

        result = component._build_embeddings("sentence-transformers/all-MiniLM-L6-v2", None)

        mock_hf_embeddings.assert_called_once_with(model="sentence-transformers/all-MiniLM-L6-v2")
        assert result == mock_embeddings

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_build_embeddings_openai(self, mock_openai_embeddings, component_class, default_kwargs):
        """Test building OpenAI embeddings."""
        component = component_class(**default_kwargs)

        mock_embeddings = MagicMock()
        mock_openai_embeddings.return_value = mock_embeddings

        result = component._build_embeddings("text-embedding-ada-002", "test-api-key")

        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-ada-002", api_key="test-api-key", chunk_size=1000
        )
        assert result == mock_embeddings

    def test_build_embeddings_openai_no_key(self, component_class, default_kwargs):
        """Test building OpenAI embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            component._build_embeddings("text-embedding-ada-002", None)

    @patch("langchain_cohere.CohereEmbeddings")
    def test_build_embeddings_cohere(self, mock_cohere_embeddings, component_class, default_kwargs):
        """Test building Cohere embeddings."""
        component = component_class(**default_kwargs)

        mock_embeddings = MagicMock()
        mock_cohere_embeddings.return_value = mock_embeddings

        result = component._build_embeddings("embed-english-v3.0", "test-api-key")

        mock_cohere_embeddings.assert_called_once_with(model="embed-english-v3.0", cohere_api_key="test-api-key")
        assert result == mock_embeddings

    def test_build_embeddings_cohere_no_key(self, component_class, default_kwargs):
        """Test building Cohere embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Cohere API key is required"):
            component._build_embeddings("embed-english-v3.0", None)

    def test_build_embeddings_custom_not_supported(self, component_class, default_kwargs):
        """Test building custom embeddings raises NotImplementedError."""
        component = component_class(**default_kwargs)

        with pytest.raises(NotImplementedError, match="Custom embedding models not yet supported"):
            component._build_embeddings("custom-model", "test-key")

    @patch("langflow.components.data.kb_ingest.get_settings_service")
    @patch("langflow.components.data.kb_ingest.encrypt_api_key")
    def test_build_embedding_metadata(self, mock_encrypt, mock_get_settings, component_class, default_kwargs):
        """Test building embedding metadata."""
        component = component_class(**default_kwargs)

        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_encrypt.return_value = "encrypted_key"

        metadata = component._build_embedding_metadata("sentence-transformers/all-MiniLM-L6-v2", "test-key")

        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert metadata["api_key"] == "encrypted_key"
        assert metadata["api_key_used"] is True
        assert metadata["chunk_size"] == 1000
        assert "created_at" in metadata

    def test_build_column_metadata(self, component_class, default_kwargs):
        """Test building column metadata."""
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        metadata = component._build_column_metadata(config_list, data_df)

        assert metadata["total_columns"] == 3
        assert metadata["mapped_columns"] == 3
        assert metadata["unmapped_columns"] == 0
        assert len(metadata["columns"]) == 3
        assert "text" in metadata["summary"]["vectorized_columns"]
        assert "category" in metadata["summary"]["identifier_columns"]

    def test_convert_df_to_data_objects(self, component_class, default_kwargs):
        """Test converting DataFrame to Data objects."""
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        # Mock Chroma to avoid actual vector store operations
        with patch("langflow.components.data.kb_ingest.Chroma") as mock_chroma:
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": []}
            mock_chroma.return_value = mock_chroma_instance

            data_objects = component._convert_df_to_data_objects(data_df, config_list)

        assert len(data_objects) == 2
        assert all(isinstance(obj, Data) for obj in data_objects)

        # Check first data object
        first_obj = data_objects[0]
        assert "text" in first_obj.data
        assert "title" in first_obj.data
        assert "category" in first_obj.data
        assert "_id" in first_obj.data

    def test_convert_df_to_data_objects_no_duplicates(self, component_class, default_kwargs):
        """Test converting DataFrame to Data objects with duplicate prevention."""
        default_kwargs["allow_duplicates"] = False
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        # Mock Chroma with existing hash
        with patch("langflow.components.data.kb_ingest.Chroma") as mock_chroma:
            # Simulate existing document with same hash
            existing_hash = "some_existing_hash"
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": existing_hash}]}
            mock_chroma.return_value = mock_chroma_instance

            # Mock hashlib to return the existing hash for first row
            with patch("langflow.components.data.kb_ingest.hashlib.sha256") as mock_hash:
                mock_hash_obj = MagicMock()
                mock_hash_obj.hexdigest.side_effect = [existing_hash, "different_hash"]
                mock_hash.return_value = mock_hash_obj

                data_objects = component._convert_df_to_data_objects(data_df, config_list)

        # Should only return one object (second row) since first is duplicate
        assert len(data_objects) == 1

    def test_is_valid_collection_name(self, component_class, default_kwargs):
        """Test collection name validation."""
        component = component_class(**default_kwargs)

        # Valid names
        assert component.is_valid_collection_name("valid_name") is True
        assert component.is_valid_collection_name("valid-name") is True
        assert component.is_valid_collection_name("ValidName123") is True

        # Invalid names
        assert component.is_valid_collection_name("ab") is False  # Too short
        assert component.is_valid_collection_name("a" * 64) is False  # Too long
        assert component.is_valid_collection_name("_invalid") is False  # Starts with underscore
        assert component.is_valid_collection_name("invalid_") is False  # Ends with underscore
        assert component.is_valid_collection_name("invalid@name") is False  # Invalid character

    @patch("langflow.components.data.kb_ingest.json.loads")
    @patch("langflow.components.data.kb_ingest.decrypt_api_key")
    def test_build_kb_info_success(self, mock_decrypt, mock_json_loads, component_class, default_kwargs):
        """Test successful KB info building."""
        component = component_class(**default_kwargs)

        # Mock metadata loading
        mock_json_loads.return_value = {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "api_key": "encrypted_key",
        }
        mock_decrypt.return_value = "decrypted_key"

        # Mock vector store creation
        with patch.object(component, "_create_vector_store"), patch.object(component, "_save_kb_files"):
            result = component.build_kb_info()

        assert isinstance(result, Data)
        assert "kb_id" in result.data
        assert "kb_name" in result.data
        assert "rows" in result.data
        assert result.data["rows"] == 2

    def test_build_kb_info_with_silent_errors(self, component_class, default_kwargs):
        """Test KB info building with silent errors enabled."""
        default_kwargs["silent_errors"] = True
        component = component_class(**default_kwargs)

        # Remove the metadata file to cause an error
        kb_path = Path(default_kwargs["kb_root_path"]) / default_kwargs["knowledge_base"]
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()

        # Should not raise exception with silent_errors=True
        result = component.build_kb_info()
        assert isinstance(result, Data)
        assert "error" in result.data

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

    @patch("langflow.components.data.kb_ingest.Path.exists")
    def test_get_knowledge_bases_no_path(self, mock_exists, component_class, default_kwargs):
        """Test getting knowledge bases when path doesn't exist."""
        component = component_class(**default_kwargs)
        mock_exists.return_value = False

        kb_list = component._get_knowledge_bases()
        assert kb_list == []

    def test_update_build_config_new_kb(self, component_class, default_kwargs):
        """Test updating build config for new knowledge base creation."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": []}}

        field_value = {
            "01_new_kb_name": "new_test_kb",
            "02_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "03_api_key": None,
        }

        # Mock embedding validation
        with (
            patch.object(component, "_build_embeddings") as mock_build_emb,
            patch.object(component, "_save_embedding_metadata"),
            patch.object(component, "_get_knowledge_bases") as mock_get_kbs,
        ):
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_build_emb.return_value = mock_embeddings
            mock_get_kbs.return_value = ["new_test_kb"]

            result = component.update_build_config(build_config, field_value, "knowledge_base")

        assert result["knowledge_base"]["value"] == "new_test_kb"
        assert "new_test_kb" in result["knowledge_base"]["options"]

    def test_update_build_config_invalid_kb_name(self, component_class, default_kwargs):
        """Test updating build config with invalid KB name."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": []}}
        field_value = {
            "01_new_kb_name": "invalid@name",  # Invalid character
            "02_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "03_api_key": None,
        }

        with pytest.raises(ValueError, match="Invalid knowledge base name"):
            component.update_build_config(build_config, field_value, "knowledge_base")
