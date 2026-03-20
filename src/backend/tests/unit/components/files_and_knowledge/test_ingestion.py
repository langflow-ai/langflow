import json
from unittest.mock import MagicMock, patch

import pytest
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from lfx.base.knowledge_bases import get_knowledge_bases
from lfx.components.files_and_knowledge import KnowledgeIngestionComponent

from tests.base import ComponentTestBaseWithClient


class TestKnowledgeIngestionComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return KnowledgeIngestionComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Mock the knowledge base root path directly."""
        with patch("lfx.components.files_and_knowledge.ingestion._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
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

        # Create embedding metadata file (new format with model_selection)
        metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "model_selection": {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "provider": "HuggingFace",
                "metadata": {
                    "embedding_class": "HuggingFaceEmbeddings",
                    "param_mapping": {"model": "model_name"},
                },
            },
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

    @patch("lfx.components.files_and_knowledge.ingestion.get_settings_service")
    @patch("lfx.components.files_and_knowledge.ingestion.encrypt_api_key")
    def test_build_embedding_metadata(self, mock_encrypt, mock_get_settings, component_class, default_kwargs):
        """Test building embedding metadata."""
        component = component_class(**default_kwargs)

        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_encrypt.return_value = "encrypted_key"

        model_selection = [
            {"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace", "metadata": {}}
        ]
        metadata = component._build_embedding_metadata(model_selection, "test-key")

        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert metadata["api_key"] == "encrypted_key"  # pragma:allowlist secret
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
        with patch("lfx.components.files_and_knowledge.ingestion.Chroma") as mock_chroma:
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
        with patch("lfx.components.files_and_knowledge.ingestion.Chroma") as mock_chroma:
            # Simulate existing document with same hash
            existing_hash = "some_existing_hash"
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": existing_hash}]}
            mock_chroma.return_value = mock_chroma_instance

            # Mock hashlib to return the existing hash for first row
            with patch("lfx.components.files_and_knowledge.ingestion.hashlib.sha256") as mock_hash:
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

    @patch("lfx.components.files_and_knowledge.ingestion.get_embeddings")
    async def test_build_kb_info_success(self, mock_get_embeddings, component_class, default_kwargs):
        """Test successful KB info building."""
        component = component_class(**default_kwargs)

        mock_embedding_fn = MagicMock()
        mock_get_embeddings.return_value = mock_embedding_fn

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

    @patch("lfx.components.files_and_knowledge.ingestion.get_embeddings")
    async def test_update_build_config_new_kb(self, mock_get_embeddings, component_class, default_kwargs):
        """Test updating build config for new knowledge base creation."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": [], "dialog_inputs": {}}}

        model_selection = [
            {"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace", "metadata": {}}
        ]
        field_value = {
            "01_new_kb_name": "new_test_kb",
            "02_embedding_model": model_selection,
            "03_api_key": "test-key",
        }

        # Mock embedding validation
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_get_embeddings.return_value = mock_embeddings

        with patch.object(component, "_save_embedding_metadata") as mock_save_metadata:
            result = await component.update_build_config(build_config, field_value, "knowledge_base")

        assert result["knowledge_base"]["value"] == "new_test_kb"
        assert "new_test_kb" in result["knowledge_base"]["options"]
        assert mock_get_embeddings.call_args.kwargs["api_key"] == "test-key"
        assert mock_save_metadata.call_args.kwargs["api_key"] == "test-key"

    @patch("lfx.components.files_and_knowledge.ingestion.get_embeddings")
    async def test_build_kb_info_with_message_input(self, mock_get_embeddings, component_class, default_kwargs):
        """Test that Message input is accepted and converted to DataFrame."""
        # Replace the DataFrame input with a Message
        default_kwargs["input_df"] = Message(text="Sample text 1")
        default_kwargs["column_config"] = [
            {"column_name": "text", "vectorize": True, "identifier": True},
        ]
        component = component_class(**default_kwargs)

        mock_embedding_fn = MagicMock()
        mock_get_embeddings.return_value = mock_embedding_fn

        with patch.object(component, "_create_vector_store"), patch.object(component, "_save_kb_files"):
            result = await component.build_kb_info()

        assert isinstance(result, Data)
        assert result.data["rows"] == 1
        assert result.data["kb_name"] == "test_kb"

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

    @patch("lfx.components.files_and_knowledge.ingestion.get_embeddings")
    async def test_build_kb_info_with_new_format_metadata(
        self, mock_get_embeddings, component_class, default_kwargs, tmp_path, active_user
    ):
        """Test that build_kb_info uses model_selection directly from new-format metadata."""
        # Overwrite the default metadata file to use the new format (includes model_selection key).
        # The old format only had embedding_model/embedding_provider strings; the new format
        # stores the full model_selection dict so get_embeddings() can reconstruct the client.
        kb_path = tmp_path / active_user.username / "test_kb"
        new_format_metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "model_selection": {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "provider": "HuggingFace",
                "metadata": {},
            },
            "api_key": None,
            "api_key_used": False,
            "chunk_size": 1000,
            "created_at": "2024-01-01T00:00:00Z",
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(new_format_metadata))

        component = component_class(**default_kwargs)
        mock_get_embeddings.return_value = MagicMock()

        with patch.object(component, "_create_vector_store"), patch.object(component, "_save_kb_files"):
            result = await component.build_kb_info()

        assert isinstance(result, Data)
        assert result.data["rows"] == 2

        # Verify get_embeddings was called with the full model_selection from the new-format metadata,
        # not a minimal reconstructed dict from the backward-compat path.
        call_kwargs = mock_get_embeddings.call_args
        passed_model = call_kwargs.kwargs.get("model") or call_kwargs.args[0]
        assert isinstance(passed_model, list)
        assert passed_model[0]["name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert passed_model[0]["provider"] == "HuggingFace"

    async def test_convert_df_to_data_objects_allow_duplicates(self, component_class, default_kwargs):
        """Test that allow_duplicates=True returns all rows even when their hashes already exist."""
        default_kwargs["allow_duplicates"] = True
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

        with patch("lfx.components.files_and_knowledge.ingestion.Chroma") as mock_chroma:
            mock_chroma_instance = MagicMock()
            # Simulate all rows as already-existing duplicates in the store
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": "hash_1"}, {"_id": "hash_2"}]}
            mock_chroma.return_value = mock_chroma_instance

            with patch("lfx.components.files_and_knowledge.ingestion.hashlib.sha256") as mock_hash:
                mock_hash_obj = MagicMock()
                # Return hashes that match the existing IDs above
                mock_hash_obj.hexdigest.side_effect = ["hash_1", "hash_2"]
                mock_hash.return_value = mock_hash_obj

                data_objects = await component._convert_df_to_data_objects(data_df, config_list)

        # All rows should be included — duplicates are allowed
        assert len(data_objects) == 2

    async def test_build_kb_info_no_metadata_file_raises_error(
        self, component_class, default_kwargs, tmp_path, active_user
    ):
        """Test that build_kb_info raises RuntimeError when no embedding metadata file exists."""
        # Remove the metadata file so model_selection cannot be determined
        kb_path = tmp_path / active_user.username / "test_kb"
        (kb_path / "embedding_metadata.json").unlink()

        component = component_class(**default_kwargs)

        with pytest.raises(RuntimeError, match="No embedding model configuration found"):
            await component.build_kb_info()

    @patch("lfx.components.files_and_knowledge.ingestion.get_embedding_model_options")
    @patch("lfx.components.files_and_knowledge.ingestion.get_embeddings")
    async def test_build_kb_info_old_format_unrecognized_model(
        self,
        mock_get_embeddings,  # noqa: ARG002
        mock_get_options,
        component_class,
        default_kwargs,
        tmp_path,
        active_user,
    ):
        """Test that old-format metadata with an unrecognized model name raises a clear error."""
        # Overwrite metadata to use old format (no model_selection key) with a model name
        # that is not in the current registry.
        kb_path = tmp_path / active_user.username / "test_kb"
        old_format_metadata = {
            "embedding_provider": "SomeOldProvider",
            "embedding_model": "old-model-that-no-longer-exists",
            "api_key": None,
            "api_key_used": False,
            "chunk_size": 1000,
            "created_at": "2024-01-01T00:00:00Z",
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(old_format_metadata))

        # Registry returns models that do NOT include the old model name
        mock_get_options.return_value = [
            {"name": "text-embedding-3-small", "provider": "OpenAI", "metadata": {}},
        ]

        component = component_class(**default_kwargs)

        # Should raise a RuntimeError wrapping a ValueError with a clear message
        with pytest.raises(RuntimeError, match="no longer recognized"):
            await component.build_kb_info()

    def test_build_embedding_metadata_without_api_key(self, component_class, default_kwargs):
        """Test _build_embedding_metadata with no API key stores model_selection for later use."""
        component = component_class(**default_kwargs)
        model_selection = [
            {"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace", "metadata": {}}
        ]

        metadata = component._build_embedding_metadata(model_selection, api_key=None)

        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert metadata["api_key"] is None
        assert metadata["api_key_used"] is False
        # New in this PR: full model_selection is stored alongside the string fields so
        # build_kb_info() can reconstruct the embedding client without hitting the model registry.
        assert "model_selection" in metadata
        assert metadata["model_selection"]["name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert metadata["model_selection"]["provider"] == "HuggingFace"
