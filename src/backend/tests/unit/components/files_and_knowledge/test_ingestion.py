import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

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
    def mock_knowledge_base_path(self, tmp_path, monkeypatch, active_user):  # noqa: ARG002 - orders app startup
        """Pin the KB root at a fresh tmp dir for every test.

        The user fixture starts the app before we patch its settings service.
        Local storage reads ``knowledge_bases_dir`` live via
        ``KBStorageHelper.get_root_path``, so the setting is what has to move.
        """
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
        with patch("lfx.components.files_and_knowledge._kb_paths._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    async def default_kwargs(self, tmp_path, active_user, mock_knowledge_base_path):  # noqa: ARG002 - orders storage root
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

        kb_name = "test_kb"
        # Creation initializes the UUID-routed SQLite store and its metadata.
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

    @pytest.fixture
    def skipped_outputs(self):
        return {
            "dataframe_output": "embeds the rows with a live embedding provider",
        }

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
    async def test_legacy_kb_path_rejects_paths_outside_the_current_user_directory(
        self, component_class, default_kwargs, knowledge_base
    ):
        from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
        from langflow.services.deps import session_scope

        # Seed a historical malformed row directly. Current creation rejects
        # this name before the legacy containment guard can be reached.
        record = KnowledgeBaseRecord(
            user_id=default_kwargs["_user_id"],
            name=knowledge_base,
            backend_type="chroma",
            model_selection={"name": "m", "provider": "HuggingFace"},
        )
        async with session_scope() as session:
            session.add(record)
            await session.commit()
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

    # Column Configuration cells hold real booleans when toggled, but a typed
    # cell (or a flow saved before the cell rendered as a toggle) keeps the raw
    # string, so every spelling the table can store must read the same way.
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (True, True),
            ("True", True),
            ("true", True),
            ("TRUE", True),
            (" true ", True),
            ("1", True),
            ("yes", True),
            (False, False),
            ("False", False),
            ("false", False),
            ("0", False),
            ("no", False),
            ("", False),
            (None, False),
        ],
    )
    def test_build_column_metadata_reads_string_flags(self, component_class, default_kwargs, raw, expected):
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = [{"column_name": "text", "vectorize": raw, "identifier": raw}]

        metadata = component._build_column_metadata(config_list, data_df)

        assert metadata["columns"] == [{"name": "text", "vectorize": expected, "identifier": expected}]
        assert metadata["summary"] == {
            "vectorized_columns": ["text"] if expected else [],
            "identifier_columns": ["text"] if expected else [],
        }

    async def test_typed_vectorize_flag_reaches_the_embedding(self, component_class, default_kwargs):
        """A Vectorize cell typed as ``"true"`` contributes to page content instead of flat metadata."""
        data_df = DataFrame(
            {
                "question": ["What is Langflow?"],
                "answer": ["A visual framework for building AI workflows"],
                "category": ["general"],
                "language": ["en"],
            }
        )
        # The saved-flow shape: untouched cells stay booleans, typed cells are strings.
        default_kwargs["input_df"] = data_df
        default_kwargs["column_config"] = [
            {"column_name": "question", "vectorize": True, "identifier": "true"},
            {"column_name": "answer", "vectorize": "true", "identifier": "false"},
        ]
        component = component_class(**default_kwargs)

        config_list = component._validate_column_config(data_df)
        metadata = component._build_column_metadata(config_list, data_df)
        [data_obj] = await component._convert_df_to_data_objects(data_df, config_list)

        assert metadata["summary"] == {
            "vectorized_columns": ["question", "answer"],
            "identifier_columns": ["question"],
        }
        assert data_obj.data["text"] == "What is Langflow? A visual framework for building AI workflows"
        assert "answer" not in data_obj.data
        assert data_obj.data["category"] == "general"
        assert data_obj.data["language"] == "en"
        # The identifier column alone keys the row.
        assert data_obj.data["_id"] == hashlib.sha256(b"What is Langflow?").hexdigest()

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_new_kb_record_persists_boolean_column_flags(
        self, mock_get_embeddings, component_class, default_kwargs
    ):
        """The KB row stores canonical booleans, so later readers never re-parse typed strings."""
        from langflow.api.utils import knowledge_base_service

        default_kwargs["column_config"] = [
            {"column_name": "question", "vectorize": True, "identifier": "true"},
            {"column_name": "answer", "vectorize": "true", "identifier": "false"},
        ]
        component = component_class(**default_kwargs)
        mock_get_embeddings.return_value.embed_query.return_value = [0.1, 0.2, 0.3]
        field_value = {
            "01_new_kb_name": "typed_flags_kb",
            "02_embedding_model": [
                {"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace", "metadata": {}}
            ],
            "03_knowledge_backend": {"backend_type": "sqlite", "backend_config": {}},
        }
        build_config = {"knowledge_base": {"value": None, "options": [], "dialog_inputs": {}}}

        await component.update_build_config(build_config, field_value, "knowledge_base")

        record = await knowledge_base_service.get_by_user_and_name(default_kwargs["_user_id"], "typed_flags_kb")
        assert record is not None
        assert record.column_config == [
            {"column_name": "question", "vectorize": True, "identifier": True},
            {"column_name": "answer", "vectorize": True, "identifier": False},
        ]
        # The component's own input is left untouched.
        assert component.column_config[1]["vectorize"] == "true"

    async def test_convert_df_to_data_objects(self, component_class, default_kwargs):
        """Test converting DataFrame to Data objects."""
        component = component_class(**default_kwargs)
        data_df = default_kwargs["input_df"]
        config_list = default_kwargs["column_config"]

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

        # The storage operation supplies existing identifiers to the converter.
        existing_hash = hashlib.sha256(b"cat1").hexdigest()
        data_objects = await component._convert_df_to_data_objects(data_df, config_list, existing_ids={existing_hash})

        # Should only return one object (second row) since first is duplicate
        assert len(data_objects) == 1
        assert data_objects[0].data["category"] == "cat2"

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

        # Isolate metadata building from storage and its statistics refresh.
        with (
            patch.object(component, "_create_vector_store"),
            patch.object(component, "_refresh_kb_stats"),
        ):
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
            "03_knowledge_backend": {"backend_type": "sqlite", "backend_config": {}},
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
        assert mock_create_record.call_args.kwargs["backend_type"] == "sqlite"
        assert mock_create_record.call_args.kwargs["backend_config"] == {}

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_update_build_config_new_kb_rejects_storage_routing_for_regular_users(
        self, mock_get_embeddings, component_class, default_kwargs
    ):
        """A regular user cannot point a component-created KB at a named index."""
        from lfx.base.knowledge_bases.backends.naming import StorageRoutingNotAllowedError

        component = component_class(**default_kwargs)
        build_config = {"knowledge_base": {"value": None, "options": [], "dialog_inputs": {}}}
        field_value = {
            "01_new_kb_name": "opensearch_test_kb",
            "02_embedding_model": [{"name": "sentence-transformers/all-MiniLM-L6-v2", "provider": "HuggingFace"}],
            "03_knowledge_backend": {
                "backend_type": "opensearch",
                "backend_config": {"url_variable": "OPENSEARCH_URL", "index_name": "kb-index"},
            },
        }

        with (
            patch.object(component, "_create_knowledge_base_record") as mock_create_record,
            pytest.raises(StorageRoutingNotAllowedError, match="index_name"),
        ):
            await component.update_build_config(build_config, field_value, "knowledge_base")

        mock_create_record.assert_not_called()
        mock_get_embeddings.assert_not_called()

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_update_build_config_new_kb_persists_backend_selection(
        self, mock_get_embeddings, component_class, default_kwargs, active_user
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

        # Only a superuser may name the index a KB uses.
        superuser = MagicMock(username=active_user.username, is_superuser=True)
        with (
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                new=AsyncMock(return_value=superuser),
            ),
            patch.object(component, "_create_knowledge_base_record") as mock_create_record,
        ):
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

        with (
            patch.object(component, "_create_vector_store"),
            patch.object(component, "_refresh_kb_stats"),
        ):
            result = await component.build_kb_info()

        assert isinstance(result, Data)
        assert result.data["rows"] == 1
        assert result.data["kb_name"] == "test_kb"

    async def test_update_build_config_invalid_kb_name(self, component_class, default_kwargs):
        """Test updating build config with invalid KB name."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": None, "options": []}}
        field_value = {
            "01_new_kb_name": "../outside",
            "02_embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "03_knowledge_backend": {"backend_type": "sqlite", "backend_config": {}},
        }

        with pytest.raises(ValueError, match="KB name contains a path separator"):
            await component.update_build_config(build_config, field_value, "knowledge_base")

    @patch("lfx.components.files_and_knowledge.knowledge.get_embeddings")
    async def test_build_kb_info_with_new_format_metadata(self, mock_get_embeddings, component_class, default_kwargs):
        """Test that build_kb_info uses ``model_selection`` straight off the KB row."""
        component = component_class(**default_kwargs)
        mock_get_embeddings.return_value = MagicMock()

        with (
            patch.object(component, "_create_vector_store"),
            patch.object(component, "_refresh_kb_stats"),
        ):
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

        existing_ids = {hashlib.sha256(category.encode()).hexdigest() for category in ("cat1", "cat2")}
        data_objects = await component._convert_df_to_data_objects(data_df, config_list, existing_ids=existing_ids)

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

        # This should NOT raise "truth value of an empty array is ambiguous"
        data_objects = await component._convert_df_to_data_objects(data_df, config_list)

        assert len(data_objects) == 2
        assert all(isinstance(obj, Data) for obj in data_objects)


class _RemoteBackendStub:
    """A backend that records how ingestion reads and writes it."""

    def __init__(self, stored_ids: set[str] | None = None) -> None:
        self.stored_ids = set(stored_ids or ())
        self.lookups: list[set[str]] = []
        self.written: list = []
        self.scanned = False
        self.size = 4096
        # Hashes another run stores while this one is embedding.
        self.stored_during_embedding: set[str] = set()

    async def ensure_ready(self) -> None:
        return None

    async def existing_content_ids(self, content_ids) -> set[str]:
        self.lookups.append(set(content_ids))
        return self.stored_ids & set(content_ids)

    async def iter_documents(self, **_kwargs):
        self.scanned = True
        if False:  # pragma: no cover — keeps this an async generator
            yield []

    async def add_embedded_documents(self, documents) -> None:
        self.written.extend(documents)

    async def storage_size_bytes(self) -> int:
        return self.size

    def embeddings(self) -> MagicMock:
        async def embed(texts):
            self.stored_ids |= self.stored_during_embedding
            return [[0.1, 0.2] for _ in texts]

        embedding_function = MagicMock()
        embedding_function.aembed_documents = AsyncMock(side_effect=embed)
        return embedding_function


@pytest.mark.usefixtures("client")
class TestIngestionReadsOnlyNewRows:
    """Deduplication and stats must cost what one run writes, not what the KB holds."""

    @pytest.fixture
    def component_class(self):
        return KnowledgeIngestionComponent

    @pytest.fixture
    async def default_kwargs(self, active_user):
        from langflow.api.utils import knowledge_base_service

        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="remote_kb",
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            backend_type="postgres",
            backend_config={},
        )
        return {
            "knowledge_base": "remote_kb",
            "input_df": DataFrame({"text": ["alpha beta", "gamma", "delta epsilon zeta"]}),
            "column_config": [{"column_name": "text", "vectorize": True, "identifier": False}],
            "chunk_size": 1000,
            "api_key": None,
            "allow_duplicates": False,
            "silent_errors": False,
            "_user_id": active_user.id,
            "_record_id": record.id,
        }

    def _component(self, component_class, kwargs):
        kwargs = dict(kwargs)
        kwargs.pop("_record_id")
        return component_class(**kwargs)

    async def _ingest(self, component, backend: _RemoteBackendStub):
        df = component.input_df
        config_list = component._validate_column_config(df)
        with patch("langflow.api.utils.kb_helpers.backend_for_name", AsyncMock(return_value=backend)):
            return await component._create_vector_store(df, config_list, embedding_function=backend.embeddings())

    @staticmethod
    def _hashes(*texts: str) -> set[str]:
        return {hashlib.sha256(text.encode()).hexdigest() for text in texts}

    async def test_skips_stored_rows_by_looking_up_only_their_hashes(self, component_class, default_kwargs):
        backend = _RemoteBackendStub(stored_ids=self._hashes("gamma") | {"some-other-chunk"})
        component = self._component(component_class, default_kwargs)

        await self._ingest(component, backend)

        # Once before embedding, then only the remaining rows again under the write lease.
        assert backend.lookups == [
            self._hashes("alpha beta", "gamma", "delta epsilon zeta"),
            self._hashes("alpha beta", "delta epsilon zeta"),
        ]
        assert backend.scanned is False
        assert [doc.content for doc in backend.written] == ["alpha beta", "delta epsilon zeta"]
        assert component._written_totals.chunks == 2
        assert component._written_totals.words == 5
        assert component._written_totals.characters == len("alpha beta") + len("delta epsilon zeta")

    async def test_skips_rows_another_run_stored_while_embedding(self, component_class, default_kwargs):
        backend = _RemoteBackendStub()
        backend.stored_during_embedding = self._hashes("gamma")
        component = self._component(component_class, default_kwargs)

        await self._ingest(component, backend)

        assert backend.scanned is False
        assert [doc.content for doc in backend.written] == ["alpha beta", "delta epsilon zeta"]
        assert component._written_totals.chunks == 2

    async def test_allow_duplicates_writes_every_row_without_a_lookup(self, component_class, default_kwargs):
        default_kwargs["allow_duplicates"] = True
        backend = _RemoteBackendStub(stored_ids=self._hashes("gamma"))
        component = self._component(component_class, default_kwargs)

        await self._ingest(component, backend)

        assert backend.lookups == []
        assert backend.scanned is False
        assert len(backend.written) == 3
        assert component._written_totals.chunks == 3

    async def test_stats_add_this_runs_totals_without_reading_the_kb(self, component_class, default_kwargs):
        from langflow.api.utils import knowledge_base_service
        from lfx.components.files_and_knowledge.knowledge import _WrittenTotals

        record_id = default_kwargs["_record_id"]
        await knowledge_base_service.update_stats(record_id, chunks=10, words=40, characters=200, source_types=["pdf"])
        component = self._component(component_class, default_kwargs)
        backend = _RemoteBackendStub()

        await component._refresh_kb_stats(
            kb_record_id=record_id,
            backend=backend,
            extensions={"txt"},
            written=_WrittenTotals(chunks=3, words=7, characters=30),
        )
        await component._refresh_kb_stats(
            kb_record_id=record_id,
            backend=backend,
            extensions={"txt"},
            written=_WrittenTotals(chunks=2, words=4, characters=11),
        )

        row = await knowledge_base_service.get_by_id(record_id)
        assert (row.chunks, row.words, row.characters) == (15, 51, 241)
        assert row.size_bytes == 4096
        assert row.source_types == ["pdf", "txt"]
        assert backend.scanned is False

    async def test_concurrent_runs_do_not_overwrite_each_others_counts(self, default_kwargs):
        import asyncio

        from langflow.api.utils import knowledge_base_service

        record_id = default_kwargs["_record_id"]
        await asyncio.gather(
            *(knowledge_base_service.increment_stats(record_id, chunks=1, words=2, characters=3) for _ in range(10))
        )

        row = await knowledge_base_service.get_by_id(record_id)
        assert (row.chunks, row.words, row.characters) == (10, 20, 30)

    async def test_stats_fall_back_to_a_recount_without_run_totals(self, component_class, default_kwargs):
        from langflow.api.utils import knowledge_base_service
        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        record_id = default_kwargs["_record_id"]
        component = self._component(component_class, default_kwargs)
        backend = _RemoteBackendStub()
        backend.count = AsyncMock(return_value=2)

        async def _iter(**_kwargs):
            yield [IngestedDocument(content="one two"), IngestedDocument(content="three")]

        backend.iter_documents = _iter

        await component._refresh_kb_stats(kb_record_id=record_id, backend=backend, extensions=set())

        row = await knowledge_base_service.get_by_id(record_id)
        assert (row.chunks, row.words, row.characters) == (2, 3, len("one two") + len("three"))
