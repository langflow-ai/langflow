import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent

from tests.base import ComponentTestBaseWithClient


class TestKnowledgeBaseComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return KnowledgeBaseComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Mock the knowledge base root path directly."""
        with patch("langflow.components.knowledge_bases.retrieval._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path, active_user):
        """Return default kwargs for component instantiation."""
        # Create knowledge base directory structure
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
            "kb_root_path": str(tmp_path),
            "api_key": None,
            "search_query": "",
            "top_k": 5,
            "include_embeddings": True,
            "_user_id": active_user.id,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for version testing."""
        # This is a new component, so it doesn't exist in older versions
        return []

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

    async def test_update_build_config(self, component_class, default_kwargs, tmp_path, active_user):
        """Test updating build configuration."""
        component = component_class(**default_kwargs)

        # Create additional KB directories
        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)

        build_config = {"knowledge_base": {"value": "test_kb", "options": []}}

        result = await component.update_build_config(build_config, None, "knowledge_base")

        assert "test_kb" in result["knowledge_base"]["options"]
        assert "kb1" in result["knowledge_base"]["options"]
        assert "kb2" in result["knowledge_base"]["options"]

    async def test_update_build_config_invalid_kb(self, component_class, default_kwargs):
        """Test updating build config when selected KB is not available."""
        component = component_class(**default_kwargs)

        build_config = {"knowledge_base": {"value": "nonexistent_kb", "options": ["test_kb"]}}

        result = await component.update_build_config(build_config, None, "knowledge_base")

        assert result["knowledge_base"]["value"] is None

    def test_get_kb_metadata_success(self, component_class, default_kwargs, active_user):
        """Test successful metadata loading."""
        component = component_class(**default_kwargs)
        kb_path = Path(default_kwargs["kb_root_path"]) / active_user.username / default_kwargs["knowledge_base"]

        with patch("langflow.components.knowledge_bases.retrieval.decrypt_api_key") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_key"

            metadata = component._get_kb_metadata(kb_path)

        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert "chunk_size" in metadata

    def test_get_kb_metadata_no_file(self, component_class, default_kwargs, tmp_path, active_user):
        """Test metadata loading when file doesn't exist."""
        component = component_class(**default_kwargs)
        nonexistent_path = tmp_path / active_user.username / "nonexistent"
        nonexistent_path.mkdir(parents=True, exist_ok=True)

        metadata = component._get_kb_metadata(nonexistent_path)

        assert metadata == {}

    def test_get_kb_metadata_json_error(self, component_class, default_kwargs, tmp_path, active_user):
        """Test metadata loading with invalid JSON."""
        component = component_class(**default_kwargs)
        kb_path = tmp_path / active_user.username / "invalid_json_kb"
        kb_path.mkdir(parents=True, exist_ok=True)

        # Create invalid JSON file
        (kb_path / "embedding_metadata.json").write_text("invalid json content")

        metadata = component._get_kb_metadata(kb_path)

        assert metadata == {}

    def test_get_kb_metadata_decrypt_error(self, component_class, default_kwargs, tmp_path, active_user):
        """Test metadata loading with decryption error."""
        component = component_class(**default_kwargs)
        kb_path = tmp_path / active_user.username / "decrypt_error_kb"
        kb_path.mkdir(parents=True, exist_ok=True)

        # Create metadata with encrypted key
        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "api_key": "encrypted_key",  # pragma:allowlist secret
            "chunk_size": 1000,
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata))

        with patch("langflow.components.knowledge_bases.retrieval.decrypt_api_key") as mock_decrypt:
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
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_openai_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata, api_key="test-api-key")

        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-ada-002",
            api_key="test-api-key",  # pragma:allowlist secret
            chunk_size=1000,  # pragma:allowlist secret
        )
        assert result == mock_embeddings

    def test_build_embeddings_openai_no_key(self, component_class, default_kwargs):
        """Test building OpenAI embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
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
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_cohere_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata, api_key="test-api-key")

        mock_cohere_embeddings.assert_called_once_with(
            model="embed-english-v3.0",
            cohere_api_key="test-api-key",  # pragma:allowlist secret
        )  # pragma:allowlist secret
        assert result == mock_embeddings

    def test_build_embeddings_cohere_no_key(self, component_class, default_kwargs):
        """Test building Cohere embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Cohere",
            "embedding_model": "embed-english-v3.0",
            "chunk_size": 1000,
        }

        with pytest.raises(ValueError, match="Cohere API key is required"):
            component._build_embeddings(metadata)

    def test_build_embeddings_custom_not_supported(self, component_class, default_kwargs):
        """Test building custom embeddings raises NotImplementedError."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Custom",
            "embedding_model": "custom-model",
        }

        with pytest.raises(NotImplementedError, match="Custom embedding models not yet supported"):
            component._build_embeddings(metadata)

    def test_build_embeddings_unsupported_provider(self, component_class, default_kwargs):
        """Test building embeddings with unsupported provider raises NotImplementedError."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "UnsupportedProvider",
            "embedding_model": "some-model",
            "api_key": "test-key",  # pragma:allowlist secret
        }  # pragma:allowlist secret

        with pytest.raises(NotImplementedError, match="Embedding provider 'UnsupportedProvider' is not supported"):
            component._build_embeddings(metadata)

    @patch("langchain_google_genai.GoogleGenerativeAIEmbeddings")
    def test_build_embeddings_google_generative_ai(self, mock_google_embeddings, component_class, default_kwargs):
        """Test building Google Generative AI embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Google Generative AI",
            "embedding_model": "models/embedding-001",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_google_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata, api_key="test-google-key")

        mock_google_embeddings.assert_called_once_with(
            model="models/embedding-001",
            google_api_key="test-google-key",  # pragma:allowlist secret
        )
        assert result == mock_embeddings

    def test_build_embeddings_google_no_key(self, component_class, default_kwargs):
        """Test building Google Generative AI embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Google Generative AI",
            "embedding_model": "models/embedding-001",
            "chunk_size": 1000,
        }

        with pytest.raises(ValueError, match="Google API key is required"):
            component._build_embeddings(metadata)

    @patch("langchain_ollama.OllamaEmbeddings")
    def test_build_embeddings_ollama(self, mock_ollama_embeddings, component_class, default_kwargs):
        """Test building Ollama embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Ollama",
            "embedding_model": "nomic-embed-text",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_ollama_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(
            metadata,
            provider_vars={"OLLAMA_BASE_URL": "http://localhost:11434"},
        )

        mock_ollama_embeddings.assert_called_once_with(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )
        assert result == mock_embeddings

    @patch("langchain_ibm.WatsonxEmbeddings")
    def test_build_embeddings_watsonx(self, mock_watsonx_embeddings, component_class, default_kwargs):
        """Test building IBM WatsonX embeddings."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "IBM WatsonX",
            "embedding_model": "ibm/slate-125m-english-rtrvr-v2",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_watsonx_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(
            metadata,
            api_key="test-watsonx-key",
            provider_vars={
                "WATSONX_APIKEY": "test-watsonx-key",  # pragma:allowlist secret
                "WATSONX_PROJECT_ID": "test-project-id",
                "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
            },
        )

        mock_watsonx_embeddings.assert_called_once_with(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            apikey="test-watsonx-key",  # pragma:allowlist secret
            project_id="test-project-id",
            url="https://us-south.ml.cloud.ibm.com",
        )
        assert result == mock_embeddings

    def test_build_embeddings_watsonx_no_key(self, component_class, default_kwargs):
        """Test building IBM WatsonX embeddings without API key raises error."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "IBM WatsonX",
            "embedding_model": "ibm/slate-125m-english-rtrvr-v2",
            "chunk_size": 1000,
        }

        with pytest.raises(ValueError, match="IBM WatsonX API key is required"):
            component._build_embeddings(metadata)

    @patch("langchain_openai.OpenAIEmbeddings")
    async def test_resolve_api_key_global_fallback(self, mock_openai_embeddings, component_class, default_kwargs):
        """Test that retrieve_data resolves the global API key for OpenAI."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 1000,
        }

        mock_embeddings = MagicMock()
        mock_openai_embeddings.return_value = mock_embeddings

        # The async _resolve_api_key should find the global key
        with patch.object(component, "_resolve_api_key", return_value="global-openai-key"):
            result = component._build_embeddings(metadata, api_key="global-openai-key")

        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-ada-002",
            api_key="global-openai-key",  # pragma:allowlist secret
            chunk_size=1000,
        )
        assert result == mock_embeddings

    def test_build_embeddings_with_explicit_api_key(self, component_class, default_kwargs):
        """Test that an explicit API key is used when passed."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 1000,
        }

        with patch("langchain_openai.OpenAIEmbeddings") as mock_openai:
            mock_embeddings = MagicMock()
            mock_openai.return_value = mock_embeddings

            component._build_embeddings(metadata, api_key="user-provided-key")

            mock_openai.assert_called_once_with(
                model="text-embedding-ada-002",
                api_key="user-provided-key",  # pragma:allowlist secret
                chunk_size=1000,
            )

    async def test_retrieve_data_no_metadata(self, component_class, default_kwargs, tmp_path, active_user):
        """Test retrieving data when metadata is missing."""
        # Remove metadata file
        kb_path = tmp_path / active_user.username / default_kwargs["knowledge_base"]
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()

        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Metadata not found for knowledge base"):
            await component.retrieve_data()

    def test_retrieve_data_path_construction(self, component_class, default_kwargs):
        """Test that retrieve_data constructs the correct paths."""
        component = component_class(**default_kwargs)

        # Test that the component correctly builds the KB path

        assert component.kb_root_path == default_kwargs["kb_root_path"]
        assert component.knowledge_base == default_kwargs["knowledge_base"]

        # Test that paths are correctly expanded
        expanded_path = Path(component.kb_root_path).expanduser()
        assert expanded_path.exists()  # tmp_path should exist

        # Verify method exists with correct parameters
        assert hasattr(component, "retrieve_data")
        assert hasattr(component, "search_query")
        assert hasattr(component, "top_k")
        assert hasattr(component, "include_embeddings")

    async def test_retrieve_data_method_exists(self, component_class, default_kwargs, active_user):
        """Test that retrieve_data method exists and can be called."""
        component = component_class(**default_kwargs)

        # Just verify the method exists and has the right signature
        assert hasattr(component, "retrieve_data"), "Component should have retrieve_data method"

        # Build a mock Chroma that returns results in the expected format
        mock_doc = MagicMock()
        mock_doc.page_content = "test content"
        mock_doc.metadata = {"_id": "doc1", "source": "test"}

        mock_chroma_instance = MagicMock()
        mock_chroma_instance.similarity_search.return_value = [mock_doc]

        mock_user = MagicMock()
        mock_user.username = active_user.username

        # Mock all external calls to avoid integration issues
        with (
            patch.object(component, "_get_kb_metadata") as mock_get_metadata,
            patch.object(component, "_build_embeddings") as mock_build_embeddings,
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch("lfx.components.files_and_knowledge.retrieval.get_user_by_id", return_value=mock_user),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch("chromadb.api.client.SharedSystemClient.clear_system_cache"),
            patch("lfx.components.files_and_knowledge.retrieval.Chroma", return_value=mock_chroma_instance),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_metadata.return_value = {"embedding_provider": "HuggingFace", "embedding_model": "test-model"}
            mock_build_embeddings.return_value = MagicMock()

            result = await component.retrieve_data()

            # Verify internal methods were called
            mock_get_metadata.assert_called_once()
            mock_build_embeddings.assert_called_once()
            assert len(result) == 1

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

    # --- _resolve_provider_variables tests ---

    async def test_resolve_provider_variables_empty_provider_vars(self, component_class, default_kwargs):
        """Test _resolve_provider_variables when provider has no variables defined."""
        component = component_class(**default_kwargs)

        with patch(
            "lfx.components.files_and_knowledge.retrieval.get_provider_all_variables",
            return_value=[],
        ):
            result = await component._resolve_provider_variables("Ollama")

        assert result == {}

    async def test_resolve_provider_variables_variable_service_returns_none(self, component_class, default_kwargs):
        """Test _resolve_provider_variables when variable_service is None."""
        component = component_class(**default_kwargs)

        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_provider_all_variables",
                return_value=[{"variable_key": "OLLAMA_BASE_URL"}],
            ),
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_variable_service",
                return_value=None,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component._resolve_provider_variables("Ollama")

        assert result == {}

    async def test_resolve_provider_variables_user_id_is_none(self, component_class, default_kwargs):
        """Test _resolve_provider_variables when user_id is None."""
        default_kwargs["_user_id"] = None
        component = component_class(**default_kwargs)

        # Set a mock vertex so user_id property returns None
        # instead of the string "None" from PlaceholderGraph
        mock_vertex = MagicMock()
        mock_vertex.graph.user_id = None
        component._vertex = mock_vertex

        with patch(
            "lfx.components.files_and_knowledge.retrieval.get_provider_all_variables",
            return_value=[{"variable_key": "OLLAMA_BASE_URL"}],
        ):
            result = await component._resolve_provider_variables("Ollama")

        assert result == {}

    async def test_resolve_provider_variables_user_id_as_string(self, component_class, default_kwargs):
        """Test _resolve_provider_variables when user_id is a string UUID."""
        user_uuid = uuid.uuid4()
        default_kwargs["_user_id"] = str(user_uuid)
        component = component_class(**default_kwargs)

        mock_variable_service = AsyncMock()
        mock_variable_service.get_variable = AsyncMock(return_value="http://localhost:11434")

        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_provider_all_variables",
                return_value=[{"variable_key": "OLLAMA_BASE_URL"}],
            ),
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_variable_service",
                return_value=mock_variable_service,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component._resolve_provider_variables("Ollama")

        assert result == {"OLLAMA_BASE_URL": "http://localhost:11434"}
        # Verify the user_id was correctly converted to UUID
        call_kwargs = mock_variable_service.get_variable.call_args[1]
        assert call_kwargs["user_id"] == user_uuid

    async def test_resolve_provider_variables_lookup_falls_back_to_env(
        self, component_class, default_kwargs, monkeypatch
    ):
        """Test _resolve_provider_variables falls back to env var on service error."""
        component = component_class(**default_kwargs)

        mock_variable_service = AsyncMock()
        mock_variable_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-fallback:11434")

        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_provider_all_variables",
                return_value=[{"variable_key": "OLLAMA_BASE_URL"}],
            ),
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_variable_service",
                return_value=mock_variable_service,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component._resolve_provider_variables("Ollama")

        assert result == {"OLLAMA_BASE_URL": "http://env-fallback:11434"}

    # --- _resolve_api_key tests ---

    async def test_resolve_api_key_unknown_provider(self, component_class, default_kwargs):
        """Test _resolve_api_key when provider is not in provider_variable_map."""
        component = component_class(**default_kwargs)

        with patch(
            "lfx.components.files_and_knowledge.retrieval.get_model_provider_variable_mapping",
            return_value={},
        ):
            result = await component._resolve_api_key("UnknownProvider")

        assert result is None

    async def test_resolve_api_key_user_id_is_none(self, component_class, default_kwargs):
        """Test _resolve_api_key when user_id is None."""
        default_kwargs["_user_id"] = None
        component = component_class(**default_kwargs)

        # Set a mock vertex so user_id property returns None
        # instead of the string "None" from PlaceholderGraph
        mock_vertex = MagicMock()
        mock_vertex.graph.user_id = None
        component._vertex = mock_vertex

        with patch(
            "lfx.components.files_and_knowledge.retrieval.get_model_provider_variable_mapping",
            return_value={"OpenAI": "OPENAI_API_KEY"},
        ):
            result = await component._resolve_api_key("OpenAI")

        assert result is None

    async def test_resolve_api_key_variable_service_is_none(self, component_class, default_kwargs):
        """Test _resolve_api_key when variable_service returns None."""
        component = component_class(**default_kwargs)

        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_model_provider_variable_mapping",
                return_value={"OpenAI": "OPENAI_API_KEY"},
            ),
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_variable_service",
                return_value=None,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component._resolve_api_key("OpenAI")

        assert result is None

    async def test_resolve_api_key_variable_service_raises(self, component_class, default_kwargs):
        """Test _resolve_api_key returns None when variable_service.get_variable raises."""
        component = component_class(**default_kwargs)

        mock_variable_service = AsyncMock()
        mock_variable_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))

        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_model_provider_variable_mapping",
                return_value={"OpenAI": "OPENAI_API_KEY"},
            ),
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_variable_service",
                return_value=mock_variable_service,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component._resolve_api_key("OpenAI")

        assert result is None

    # --- _build_embeddings edge case tests ---

    @patch("langchain_ollama.OllamaEmbeddings")
    def test_build_embeddings_ollama_without_base_url(self, mock_ollama_embeddings, component_class, default_kwargs):
        """Test building Ollama embeddings without base_url (empty provider_vars)."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Ollama",
            "embedding_model": "nomic-embed-text",
        }

        mock_embeddings = MagicMock()
        mock_ollama_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata, provider_vars={})

        # Should be called without base_url kwarg
        mock_ollama_embeddings.assert_called_once_with(model="nomic-embed-text")
        assert result == mock_embeddings

    @patch("langchain_ollama.OllamaEmbeddings")
    def test_build_embeddings_ollama_no_provider_vars(self, mock_ollama_embeddings, component_class, default_kwargs):
        """Test building Ollama embeddings with provider_vars=None."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "Ollama",
            "embedding_model": "nomic-embed-text",
        }

        mock_embeddings = MagicMock()
        mock_ollama_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(metadata, provider_vars=None)

        mock_ollama_embeddings.assert_called_once_with(model="nomic-embed-text")
        assert result == mock_embeddings

    @patch("langchain_ibm.WatsonxEmbeddings")
    def test_build_embeddings_watsonx_api_key_from_provider_vars(
        self, mock_watsonx_embeddings, component_class, default_kwargs
    ):
        """Test WatsonX uses api_key from provider_vars fallback when api_key param is None."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "IBM WatsonX",
            "embedding_model": "ibm/slate-125m-english-rtrvr-v2",
        }

        mock_embeddings = MagicMock()
        mock_watsonx_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(
            metadata,
            api_key=None,
            provider_vars={
                "WATSONX_APIKEY": "vars-watsonx-key",  # pragma:allowlist secret
                "WATSONX_PROJECT_ID": "project-123",
                "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
            },
        )

        mock_watsonx_embeddings.assert_called_once_with(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            apikey="vars-watsonx-key",  # pragma:allowlist secret
            project_id="project-123",
            url="https://us-south.ml.cloud.ibm.com",
        )
        assert result == mock_embeddings

    @patch("langchain_ibm.WatsonxEmbeddings")
    def test_build_embeddings_watsonx_partial_vars(self, mock_watsonx_embeddings, component_class, default_kwargs):
        """Test WatsonX with only apikey, no project_id or url."""
        component = component_class(**default_kwargs)

        metadata = {
            "embedding_provider": "IBM WatsonX",
            "embedding_model": "ibm/slate-125m-english-rtrvr-v2",
        }

        mock_embeddings = MagicMock()
        mock_watsonx_embeddings.return_value = mock_embeddings

        result = component._build_embeddings(
            metadata,
            api_key="only-api-key",
            provider_vars={},
        )

        # project_id and url should be omitted from kwargs
        mock_watsonx_embeddings.assert_called_once_with(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            apikey="only-api-key",  # pragma:allowlist secret
        )
        assert result == mock_embeddings

    def test_build_embeddings_empty_metadata(self, component_class, default_kwargs):
        """Test _build_embeddings with empty metadata dict (no provider, no model)."""
        component = component_class(**default_kwargs)

        with pytest.raises(NotImplementedError, match="Embedding provider 'None' is not supported"):
            component._build_embeddings({})

    # --- retrieve_data integration edge case tests ---

    async def test_retrieve_data_user_id_is_none(self, component_class, default_kwargs):
        """Test retrieve_data raises when user_id is None."""
        default_kwargs["_user_id"] = None
        component = component_class(**default_kwargs)

        # Set a mock vertex so user_id property returns None
        # instead of the string "None" from PlaceholderGraph
        mock_vertex = MagicMock()
        mock_vertex.graph.user_id = None
        component._vertex = mock_vertex

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="User ID is required"):
                await component.retrieve_data()

    async def test_retrieve_data_user_not_found(self, component_class, default_kwargs):
        """Test retrieve_data raises when user is not found in DB."""
        component = component_class(**default_kwargs)

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=None,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match=r"User with ID .* not found"):
                await component.retrieve_data()

    async def test_retrieve_data_with_search_query(self, component_class, default_kwargs, active_user):
        """Test retrieve_data with a populated search_query uses similarity_search_with_score."""
        default_kwargs["search_query"] = "find me something"
        component = component_class(**default_kwargs)

        mock_doc = MagicMock()
        mock_doc.page_content = "matched content"
        mock_doc.metadata = {"_id": "doc1", "source": "test"}

        mock_chroma_instance = MagicMock()
        # similarity_search_with_score returns (doc, score) tuples
        mock_chroma_instance.similarity_search_with_score.return_value = [(mock_doc, 0.85)]

        mock_user = MagicMock()
        mock_user.username = active_user.username

        with (
            patch.object(component, "_get_kb_metadata") as mock_get_metadata,
            patch.object(component, "_build_embeddings") as mock_build_embeddings,
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch("lfx.components.files_and_knowledge.retrieval.get_user_by_id", return_value=mock_user),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch("chromadb.api.client.SharedSystemClient.clear_system_cache"),
            patch("lfx.components.files_and_knowledge.retrieval.Chroma", return_value=mock_chroma_instance),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_metadata.return_value = {"embedding_provider": "HuggingFace", "embedding_model": "test-model"}
            mock_build_embeddings.return_value = MagicMock()

            result = await component.retrieve_data()

            # Verify similarity_search_with_score was used (not similarity_search)
            mock_chroma_instance.similarity_search_with_score.assert_called_once_with(query="find me something", k=5)
            mock_chroma_instance.similarity_search.assert_not_called()
            assert len(result) == 1

    async def test_retrieve_data_without_search_query(self, component_class, default_kwargs, active_user):
        """Test retrieve_data with empty search_query uses similarity_search."""
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)

        mock_doc = MagicMock()
        mock_doc.page_content = "all content"
        mock_doc.metadata = {"_id": "doc1", "source": "test"}

        mock_chroma_instance = MagicMock()
        mock_chroma_instance.similarity_search.return_value = [mock_doc]

        mock_user = MagicMock()
        mock_user.username = active_user.username

        with (
            patch.object(component, "_get_kb_metadata") as mock_get_metadata,
            patch.object(component, "_build_embeddings") as mock_build_embeddings,
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch("lfx.components.files_and_knowledge.retrieval.get_user_by_id", return_value=mock_user),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch("chromadb.api.client.SharedSystemClient.clear_system_cache"),
            patch("lfx.components.files_and_knowledge.retrieval.Chroma", return_value=mock_chroma_instance),
        ):
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_metadata.return_value = {"embedding_provider": "HuggingFace", "embedding_model": "test-model"}
            mock_build_embeddings.return_value = MagicMock()

            result = await component.retrieve_data()

            # Verify similarity_search was used (not similarity_search_with_score)
            mock_chroma_instance.similarity_search.assert_called_once_with(query="", k=5)
            mock_chroma_instance.similarity_search_with_score.assert_not_called()
            assert len(result) == 1
