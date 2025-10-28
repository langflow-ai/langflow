import json
from unittest.mock import MagicMock, patch

import pytest
from langflow.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from langflow.components.knowledge_bases.ingestion import KnowledgeIngestionComponent
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame

from tests.base import ComponentTestBaseWithClient


class TestKnowledgeIngestionComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return KnowledgeIngestionComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Mock the knowledge base root path directly."""
        with patch("langflow.components.knowledge_bases.ingestion._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path, active_user):
        """Return default kwargs for component instantiation."""
        # Create a sample DataFrame
        data_df = DataFrame(
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
        kb_path = tmp_path / active_user.username / kb_name
        kb_path.mkdir(parents=True, exist_ok=True)

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
            "_user_id": active_user.id,
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

        # Instantiate the component with the modified config
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]

        # Should raise ValueError since column does not exist in DataFrame
        with pytest.raises(ValueError, match="Column 'nonexistent' not found in DataFrame"):
            component._validate_column_config(data_df)

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

    @patch("langflow.components.knowledge_bases.ingestion.get_settings_service")
    @patch("langflow.components.knowledge_bases.ingestion.encrypt_api_key")
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

    async def test_convert_df_to_data_objects(self, component_class, default_kwargs):
        """Test converting DataFrame to Data objects."""
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        # Mock Chroma to avoid actual vector store operations
        with patch("langflow.components.knowledge_bases.ingestion.Chroma") as mock_chroma:
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": []}
            mock_chroma.return_value = mock_chroma_instance

            data_objects = await component._convert_df_to_data_objects(data_df, config_list)

        assert len(data_objects) == 2
        assert all(isinstance(obj, Data) for obj in data_objects)

        # Check first data object
        first_obj = data_objects[0]
        assert "text" in first_obj.data
        assert "title" in first_obj.data
        assert "category" in first_obj.data
        assert "_id" in first_obj.data

    async def test_convert_df_to_data_objects_no_duplicates(self, component_class, default_kwargs):
        """Test converting DataFrame to Data objects with duplicate prevention."""
        default_kwargs["allow_duplicates"] = False
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        # Mock Chroma with existing hash
        with patch("langflow.components.knowledge_bases.ingestion.Chroma") as mock_chroma:
            # Simulate existing document with same hash
            existing_hash = "some_existing_hash"
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": existing_hash}]}
            mock_chroma.return_value = mock_chroma_instance

            # Mock hashlib to return the existing hash for first row
            with patch("langflow.components.knowledge_bases.ingestion.hashlib.sha256") as mock_hash:
                mock_hash_obj = MagicMock()
                mock_hash_obj.hexdigest.side_effect = [existing_hash, "different_hash"]
                mock_hash.return_value = mock_hash_obj

                data_objects = await component._convert_df_to_data_objects(data_df, config_list)

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

    @patch("langflow.components.knowledge_bases.ingestion.json.loads")
    @patch("langflow.components.knowledge_bases.ingestion.decrypt_api_key")
    async def test_build_kb_info_success(self, mock_decrypt, mock_json_loads, component_class, default_kwargs):
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
            result = await component.build_kb_info()

        assert isinstance(result, Data)
        assert "kb_id" in result.data
        assert "kb_name" in result.data
        assert "rows" in result.data
        assert result.data["rows"] == 2

    async def test_get_knowledge_bases(self, tmp_path, active_user):
        """Test getting list of knowledge bases."""
        # Create additional test directories
        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / ".hidden").mkdir(parents=True, exist_ok=True)  # Should be ignored

        kb_list = await get_knowledge_bases(tmp_path, user_id=active_user.id)

        assert "test_kb" in kb_list
        assert "kb1" in kb_list
        assert "kb2" in kb_list
        assert ".hidden" not in kb_list

    async def test_update_build_config_new_kb(self, component_class, default_kwargs):
        """Test updating build config for new knowledge base creation."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": []}}

        field_value = {
            "01_new_kb_name": "new_test_kb",
            "02_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "03_api_key": "abc123",  # Mock API key
        }

        # Mock embedding validation
        with (
            patch.object(component, "_build_embeddings") as mock_build_emb,
            patch.object(component, "_save_embedding_metadata"),
        ):
            mock_embeddings = MagicMock()
            mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_build_emb.return_value = mock_embeddings

            result = await component.update_build_config(build_config, field_value, "knowledge_base")

        assert result["knowledge_base"]["value"] == "new_test_kb"
        assert "new_test_kb" in result["knowledge_base"]["options"]

    async def test_update_build_config_invalid_kb_name(self, component_class, default_kwargs):
        """Test updating build config with invalid KB name."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": []}}
        field_value = {
            "01_new_kb_name": "invalid@name",  # Invalid character
            "02_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "03_api_key": None,
        }

        with pytest.raises(ValueError, match="Invalid knowledge base name"):
            await component.update_build_config(build_config, field_value, "knowledge_base")
