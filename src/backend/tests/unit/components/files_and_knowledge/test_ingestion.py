from unittest.mock import MagicMock, patch

import numpy as np
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
    def mock_knowledge_base_path(self, tmp_path, monkeypatch):
        """Pin the KB root at a fresh tmp dir for every test.

        Local-Chroma path resolution reads ``knowledge_bases_dir`` live via
        ``KBStorageHelper.get_root_path``, so the setting is what has to move.
        """
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
        with patch("lfx.components.files_and_knowledge._kb_paths._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    async def default_kwargs(self, tmp_path, active_user):
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

        # The ``knowledge_base`` row is what makes the KB exist and carries its
        # embedding config; the directory above is only where local-Chroma
        # vectors would land.
        from langflow.api.utils import knowledge_base_service

        await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=kb_name,
            model_selection={
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "provider": "HuggingFace",
                "metadata": {
                    "embedding_class": "HuggingFaceEmbeddings",
                    "param_mapping": {"model": "model_name"},
                },
            },
            chunk_size=1000,
        )

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

    @pytest.mark.parametrize("knowledge_base", ["../../outside", "../victim/secret_kb"])
    async def test_kb_path_rejects_paths_outside_the_current_user_directory(
        self, component_class, default_kwargs, knowledge_base
    ):
        from langflow.api.utils import knowledge_base_service

        # Path resolution only runs once the backend resolves, so the traversing
        # name needs a row for the containment guard to be reachable at all.
        await knowledge_base_service.create_record(
            user_id=default_kwargs["_user_id"],
            name=knowledge_base,
            model_selection={"name": "m", "provider": "HuggingFace"},
        )
        default_kwargs["knowledge_base"] = knowledge_base
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="KB path escapes root directory"):
            await component._kb_path()

    def test_new_knowledge_dialog_uses_provider_credentials(self, component_class, default_kwargs):
        """Test the create-knowledge dialog no longer exposes a redundant API key override."""
        component = component_class(**default_kwargs)
        dialog_inputs = component.inputs[0].dialog_inputs["fields"]["data"]["node"]
        embedding_model_input = dialog_inputs["template"]["02_embedding_model"]
        backend_input = dialog_inputs["template"]["03_knowledge_backend"]

        assert dialog_inputs["field_order"] == ["01_new_kb_name", "02_embedding_model", "03_knowledge_backend"]
        assert "03_api_key" not in dialog_inputs["template"]
        assert "configured credentials" in embedding_model_input.info
        assert backend_input.field_type.value == "knowledge_backend"
        assert backend_input.display_name == "DB Provider"
        # Default is empty so the frontend can populate it from the user's
        # configured active DB Provider on first render.
        assert backend_input.value == {}

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
        with patch("lfx.components.files_and_knowledge.knowledge.Chroma") as mock_chroma:
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
        with patch("lfx.components.files_and_knowledge.knowledge.Chroma") as mock_chroma:
            # Simulate existing document with same hash
            existing_hash = "some_existing_hash"
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": existing_hash}]}
            mock_chroma.return_value = mock_chroma_instance

            # Mock hashlib to return the existing hash for first row
            with patch("lfx.components.files_and_knowledge.knowledge.hashlib.sha256") as mock_hash:
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
        assert component.is_valid_collection_name("docs.v2") is True
        assert component.is_valid_collection_name("a" * 512) is True

        # Invalid names
        assert component.is_valid_collection_name("ab") is False  # Too short
        assert component.is_valid_collection_name("a" * 513) is False  # Too long
        assert component.is_valid_collection_name("_invalid") is False  # Starts with underscore
        assert component.is_valid_collection_name("invalid_") is False  # Ends with underscore
        assert component.is_valid_collection_name("invalid@name") is False  # Invalid character

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_build_kb_info_success(self, mock_get_embeddings, component_class, default_kwargs):
        """Test successful KB info building."""
        component = component_class(**default_kwargs)

        mock_embedding_fn = MagicMock()
        mock_get_embeddings.return_value = mock_embedding_fn

        # Mock vector store creation
        with patch.object(component, "_create_vector_store"):
            result = await component.build_kb_info()

        assert isinstance(result, Data)
        assert "kb_id" in result.data
        assert "kb_name" in result.data
        assert "rows" in result.data
        assert result.data["rows"] == 2

    async def test_get_knowledge_bases(self, tmp_path, active_user):
        """Test getting list of knowledge bases."""
        # Create additional test directories
        from langflow.api.utils import knowledge_base_service

        # Rows are what the dropdown lists; a bare directory is invisible.
        await knowledge_base_service.create_record(user_id=active_user.id, name="kb1")
        await knowledge_base_service.create_record(user_id=active_user.id, name="kb2")
        (tmp_path / active_user.username / "dir_without_row").mkdir(parents=True, exist_ok=True)

        kb_list = await get_knowledge_bases(user_id=active_user.id)

        assert "test_kb" in kb_list
        assert "kb1" in kb_list
        assert "kb2" in kb_list
        assert "dir_without_row" not in kb_list

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
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
            "03_knowledge_backend": {"backend_type": "chroma", "backend_config": {}},
        }

        # Mock embedding validation
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_get_embeddings.return_value = mock_embeddings

        with patch.object(
            component,
            "_create_knowledge_base_record",
            wraps=component._create_knowledge_base_record,
        ) as mock_create_record:
            result = await component.update_build_config(build_config, field_value, "knowledge_base")

        assert result["knowledge_base"]["value"] == "new_test_kb"
        assert "new_test_kb" in result["knowledge_base"]["options"]
        assert "api_key" not in mock_get_embeddings.call_args.kwargs
        assert mock_create_record.call_args.kwargs["backend_type"] == "chroma"
        assert mock_create_record.call_args.kwargs["backend_config"] == {}

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_update_build_config_new_kb_persists_backend_selection(
        self, mock_get_embeddings, component_class, default_kwargs
    ):
        """Test creating knowledge from the component dialog preserves the selected backend."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": [], "dialog_inputs": {}}}
        model_selection = [
            {"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace", "metadata": {}}
        ]
        field_value = {
            "01_new_kb_name": "opensearch_test_kb",
            "02_embedding_model": model_selection,
            "03_knowledge_backend": {
                "backend_type": "opensearch",
                "backend_config": {
                    "url_variable": "OPENSEARCH_URL",
                    "index_name": "kb-index",
                    "vector_field": "embedding",
                    "text_field": "content",
                },
            },
        }

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_get_embeddings.return_value = mock_embeddings

        with patch.object(component, "_create_knowledge_base_record") as mock_create_record:
            await component.update_build_config(build_config, field_value, "knowledge_base")

        assert mock_create_record.call_args.kwargs["backend_type"] == "opensearch"
        assert mock_create_record.call_args.kwargs["backend_config"]["index_name"] == "kb-index"
        assert mock_create_record.call_args.kwargs["backend_config"]["text_field"] == "content"

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
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

        with patch.object(component, "_create_vector_store"):
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
            "03_knowledge_backend": {"backend_type": "chroma", "backend_config": {}},
        }

        with pytest.raises(ValueError, match="Chroma naming rules"):
            await component.update_build_config(build_config, field_value, "knowledge_base")

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_build_kb_info_with_new_format_metadata(self, mock_get_embeddings, component_class, default_kwargs):
        """Test that build_kb_info uses ``model_selection`` straight off the KB row."""
        component = component_class(**default_kwargs)
        mock_get_embeddings.return_value = MagicMock()

        with patch.object(component, "_create_vector_store"):
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

        with patch("lfx.components.files_and_knowledge.knowledge.Chroma") as mock_chroma:
            mock_chroma_instance = MagicMock()
            # Simulate all rows as already-existing duplicates in the store
            mock_chroma_instance.get.return_value = {"metadatas": [{"_id": "hash_1"}, {"_id": "hash_2"}]}
            mock_chroma.return_value = mock_chroma_instance

            with patch("lfx.components.files_and_knowledge.knowledge.hashlib.sha256") as mock_hash:
                mock_hash_obj = MagicMock()
                # Return hashes that match the existing IDs above
                mock_hash_obj.hexdigest.side_effect = ["hash_1", "hash_2"]
                mock_hash.return_value = mock_hash_obj

                data_objects = await component._convert_df_to_data_objects(data_df, config_list)

        # All rows should be included — duplicates are allowed
        assert len(data_objects) == 2

    async def test_build_kb_info_without_a_kb_row_raises_error(
        self, component_class, default_kwargs, tmp_path, active_user
    ):
        """A KB with no ``knowledge_base`` row has no embedding config to ingest with."""
        (tmp_path / active_user.username / "rowless_kb").mkdir(parents=True, exist_ok=True)
        default_kwargs["knowledge_base"] = "rowless_kb"
        component = component_class(**default_kwargs)

        with pytest.raises(RuntimeError, match="No embedding model configuration found"):
            await component.build_kb_info()

    def test_scalar_notna_with_scalar_values(self, component_class, default_kwargs):
        """Test _scalar_notna returns correct results for scalar values."""
        component = component_class(**default_kwargs)

        assert component._scalar_notna("hello") is True
        assert component._scalar_notna(42) is True
        assert component._scalar_notna(0) is True
        assert component._scalar_notna("") is True
        assert component._scalar_notna(None) is False
        assert component._scalar_notna(float("nan")) is False

    def test_scalar_notna_with_numpy_arrays(self, component_class, default_kwargs):
        """Test _scalar_notna handles numpy arrays without raising ambiguous truth value errors."""
        component = component_class(**default_kwargs)

        # Empty array — should be falsy (no valid data)
        assert not component._scalar_notna(np.array([]))

        # Array with valid values — should be truthy
        assert component._scalar_notna(np.array([1, 2, 3]))

        # Array containing NaN — should be falsy (not all values are non-NA)
        assert not component._scalar_notna(np.array([1, float("nan"), 3]))

        # Array of strings — should be truthy
        assert component._scalar_notna(np.array(["a", "b"]))

    def test_scalar_notna_with_lists(self, component_class, default_kwargs):
        """Test _scalar_notna handles plain lists safely."""
        component = component_class(**default_kwargs)

        assert not component._scalar_notna([])
        assert component._scalar_notna([1, 2])

    async def test_convert_df_to_data_objects_with_array_cells(self, component_class, default_kwargs):
        """Test that _convert_df_to_data_objects handles DataFrame rows containing numpy arrays.

        This reproduces the bug where Split Text output contains metadata columns with
        array values, causing 'truth value of an empty array is ambiguous' errors.
        """
        # Build a DataFrame with an array-valued metadata column (mimics Split Text output)
        data_df = DataFrame(
            {
                "text": ["chunk 1", "chunk 2"],
                "source": ["file.txt", "file.txt"],
                "tags": [np.array([]), np.array(["important"])],
            }
        )
        default_kwargs["input_df"] = data_df
        default_kwargs["column_config"] = [
            {"column_name": "text", "vectorize": True, "identifier": False},
            {"column_name": "source", "vectorize": False, "identifier": True},
            {"column_name": "tags", "vectorize": False, "identifier": False},
        ]
        component = component_class(**default_kwargs)
        config_list = default_kwargs["column_config"]

        with patch("lfx.components.files_and_knowledge.knowledge.Chroma") as mock_chroma:
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get.return_value = {"metadatas": []}
            mock_chroma.return_value = mock_chroma_instance

            # This should NOT raise "truth value of an empty array is ambiguous"
            data_objects = await component._convert_df_to_data_objects(data_df, config_list)

        assert len(data_objects) == 2
        assert all(isinstance(obj, Data) for obj in data_objects)
