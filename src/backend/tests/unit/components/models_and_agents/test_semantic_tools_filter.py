"""Tests for SemanticToolsFilterComponent."""

from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np
import pytest
from langchain_core.tools import Tool
from lfx.components.models_and_agents.semantic_tools_filter import SemanticToolsFilterComponent

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient, VersionComponentMapping


class TestSemanticToolsFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return SemanticToolsFilterComponent

    @pytest.fixture
    def session_id(self):
        return f"test_session_{uuid4().hex}"

    @pytest.fixture
    def default_kwargs(self, session_id):
        return {
            "tools": [],
            "user_query": "test query",
            "use_embeddings": False,
            "use_reranker": False,
            "_session_id": session_id,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions.

        SemanticToolsFilter is a new component that didn't exist in previous versions.
        """
        return [
            {"version": "1.0.19", "module": "models_and_agents", "file_name": DID_NOT_EXIST},  # type: ignore[typeddict-item]
            {"version": "1.1.0", "module": "models_and_agents", "file_name": DID_NOT_EXIST},  # type: ignore[typeddict-item]
            {"version": "1.1.1", "module": "models_and_agents", "file_name": DID_NOT_EXIST},  # type: ignore[typeddict-item]
        ]

    @pytest.fixture
    def sample_tools(self):
        """Create sample tools for testing."""
        return [
            Tool(
                name="calculator",
                description="Perform arithmetic calculations",
                func=lambda x: "42",  # noqa: ARG005
            ),
            Tool(
                name="weather",
                description="Get weather information for a location",
                func=lambda x: f"Weather for {x}",
            ),
            Tool(
                name="search",
                description="Search the web for information",
                func=lambda x: f"Search results for {x}",
            ),
            Tool(
                name="translator",
                description="Translate text between languages",
                func=lambda x: f"Translated: {x}",
            ),
            Tool(
                name="calendar",
                description="Manage calendar events and schedules",
                func=lambda x: f"Calendar: {x}",
            ),
        ]

    @pytest.fixture
    def mock_embedding_model(self):
        """Create a mock embedding model."""
        mock = Mock()
        # Return deterministic embeddings based on tool descriptions
        mock.embed_documents.return_value = [
            [0.1, 0.2, 0.3],  # calculator
            [0.4, 0.5, 0.6],  # weather
            [0.7, 0.8, 0.9],  # search
            [0.2, 0.3, 0.4],  # translator
            [0.5, 0.6, 0.7],  # calendar
        ]
        mock.embed_query.return_value = [0.7, 0.8, 0.9]  # Similar to search
        return mock

    @pytest.fixture
    def mock_llm_model(self):
        """Create a mock LLM model."""
        mock = Mock()
        response = Mock()
        response.content = "[1, 3]"  # Select tools 1 and 3
        mock.invoke.return_value = response
        return mock

    def test_no_tools_provided(self, component_class, session_id):
        """Test behavior when no tools are provided."""
        component = component_class(
            tools=[],
            user_query="test query",
            use_embeddings=False,
            use_reranker=False,
            _session_id=session_id,
        )

        result = component.filter_tools()

        assert result == []
        assert "No tools provided" in component.status

    def test_pass_through_mode(self, component_class, sample_tools, session_id):
        """Test pass-through mode when both filters are disabled."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=False,
            use_reranker=False,
            _session_id=session_id,
        )

        result = component.filter_tools()

        assert len(result) == len(sample_tools)
        assert result == sample_tools
        assert "No filtering enabled" in component.status

    def test_embedding_filter_only(self, component_class, sample_tools, mock_embedding_model, session_id):
        """Test embedding filter without reranker."""
        # Clear cache to ensure fresh calls
        with patch.object(component_class, "_persistent_cache", return_value={}):
            component = component_class(
                tools=sample_tools,
                user_query="search for information",
                use_embeddings=True,
                embedding_model=mock_embedding_model,
                top_k=3,
                similarity_threshold=0.0,
                use_reranker=False,
                _session_id=session_id,
            )

            result = component.filter_tools()

            # Should return top 3 tools based on similarity
            assert len(result) <= 3
            assert all(isinstance(tool, Tool) for tool in result)
            mock_embedding_model.embed_documents.assert_called()
            mock_embedding_model.embed_query.assert_called_once()

    def test_embedding_filter_with_threshold(self, component_class, sample_tools, mock_embedding_model, session_id):
        """Test embedding filter with similarity threshold."""
        component = component_class(
            tools=sample_tools,
            user_query="search for information",
            use_embeddings=True,
            embedding_model=mock_embedding_model,
            top_k=5,
            similarity_threshold=0.5,
            use_reranker=False,
            _session_id=session_id,
        )

        result = component.filter_tools()

        # Should filter by threshold
        assert len(result) <= 5
        # Verify that filtering occurred and results were returned
        assert len(result) > 0
        assert "threshold=0.5" in component.status

    def test_reranker_only(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test LLM reranker without embedding filter."""
        component = component_class(
            tools=sample_tools,
            user_query="search for information",
            use_embeddings=False,
            use_reranker=True,
            reranker_model=mock_llm_model,
            top_p=2,
            _session_id=session_id,
        )

        result = component.filter_tools()

        # Should use reranker on all tools
        assert len(result) <= 2
        mock_llm_model.invoke.assert_called_once()

    def test_both_filters(self, component_class, sample_tools, mock_embedding_model, mock_llm_model, session_id):
        """Test both embedding filter and reranker together."""
        # Clear cache to ensure fresh calls
        with patch.object(component_class, "_persistent_cache", return_value={}):
            component = component_class(
                tools=sample_tools,
                user_query="search for information",
                use_embeddings=True,
                embedding_model=mock_embedding_model,
                top_k=3,
                use_reranker=True,
                reranker_model=mock_llm_model,
                top_p=2,
                _session_id=session_id,
            )

            result = component.filter_tools()

            # Should apply both filters
            assert len(result) <= 2
            mock_embedding_model.embed_documents.assert_called()
            mock_llm_model.invoke.assert_called_once()

    def test_missing_embedding_model_error(self, component_class, sample_tools, session_id):
        """Test error when embedding model is required but not provided."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=True,
            embedding_model=None,
            _session_id=session_id,
        )

        with pytest.raises(ValueError, match="Embedding Model must be connected"):
            component.filter_tools()

    def test_missing_reranker_model_error(self, component_class, sample_tools, session_id):
        """Test error when reranker model is required but not provided."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=False,
            use_reranker=True,
            reranker_model=None,
            _session_id=session_id,
        )

        with pytest.raises(ValueError, match="Reranker Model must be connected"):
            component.filter_tools()

    def test_invalid_top_k_error(self, component_class, sample_tools, session_id):
        """Test error when top_k is less than 1."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=True,
            embedding_model=Mock(),
            top_k=0,
            _session_id=session_id,
        )

        with pytest.raises(ValueError, match="Top K must be >= 1"):
            component.filter_tools()

    def test_invalid_top_p_error(self, component_class, sample_tools, session_id):
        """Test error when top_p is less than 1."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=False,
            use_reranker=True,
            reranker_model=Mock(),
            top_p=0,
            _session_id=session_id,
        )

        with pytest.raises(ValueError, match="Top P must be >= 1"):
            component.filter_tools()

    def test_invalid_augmentation_samples_error(self, component_class, sample_tools, session_id):
        """Test error when augmentation_samples is less than 1."""
        component = component_class(
            tools=sample_tools,
            user_query="test query",
            use_embeddings=True,
            embedding_model=Mock(),
            augment_descriptions=True,
            augmentation_model=Mock(),
            augmentation_samples=0,
            _session_id=session_id,
        )

        with pytest.raises(ValueError, match="Augmentation Samples must be >= 1"):
            component.filter_tools()

    def test_cosine_similarity_calculation(self, component_class):
        """Test cosine similarity calculation."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.5, 0.0]])

        similarities = component_class._cosine_similarity(a, b)

        assert len(similarities) == 3
        assert similarities[0] == pytest.approx(1.0)  # Same vector
        assert similarities[1] == pytest.approx(0.0)  # Orthogonal
        assert 0 < similarities[2] < 1  # Partial similarity

    def test_tools_hash_deterministic(self, component_class, sample_tools):
        """Test that tools hash is deterministic."""
        hash1 = component_class._tools_hash(sample_tools)
        hash2 = component_class._tools_hash(sample_tools)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 32  # MD5 hash length

    def test_extract_json_array(self, component_class):
        """Test JSON array extraction from text."""
        text = "Here is the result: [1, 2, 3] and some more text"
        result = component_class._extract_json_array(text)
        assert result == "[1, 2, 3]"

        # Test with code blocks
        text_with_code = "```json\n[1, 2, 3]\n```"
        result = component_class._extract_json_array(text_with_code)
        assert result == "[1, 2, 3]"

    def test_extract_json_array_error(self, component_class):
        """Test JSON array extraction error handling."""
        with pytest.raises(ValueError, match="No JSON array found"):
            component_class._extract_json_array("No array here")

        with pytest.raises(ValueError, match="Unbalanced brackets"):
            component_class._extract_json_array("[1, 2, 3")

    def test_parse_numbered_list(self, component_class):
        """Test numbered list parsing."""
        text = """
        1. First item
        2. Second item
        3. Third item
        """
        result = component_class._parse_numbered_list(text)
        assert result == ["First item", "Second item", "Third item"]

        # Test with parentheses
        text_parens = """
        1) First item
        2) Second item
        """
        result = component_class._parse_numbered_list(text_parens)
        assert result == ["First item", "Second item"]

    def test_cache_operations(self, component_class):
        """Test cache encoding and decoding."""
        # Test numpy array encoding/decoding
        arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        encoded = component_class._encode_cache_value(arr)
        assert "__ndarray__" in encoded
        decoded = component_class._decode_cache_value(encoded)
        assert isinstance(decoded, np.ndarray)
        assert np.array_equal(decoded, arr)

        # Test regular value pass-through
        regular_value = {"key": "value"}
        encoded = component_class._encode_cache_value(regular_value)
        assert encoded == regular_value
        decoded = component_class._decode_cache_value(encoded)
        assert decoded == regular_value

    def test_update_build_config(self, component_class, session_id):
        """Test dynamic field visibility based on toggles."""
        component = component_class(
            tools=[],
            user_query="test",
            use_embeddings=True,
            augment_descriptions=False,
            use_reranker=False,
            _session_id=session_id,
        )

        build_config = {
            "use_embeddings": {"value": True},
            "augment_descriptions": {"value": False},
            "use_reranker": {"value": False},
            "embedding_model": {"show": False},
            "top_k": {"show": False},
            "similarity_threshold": {"show": False},
            "augmentation_model": {"show": False},
            "augmentation_samples": {"show": False},
            "augmentation_prompt": {"show": False},
            "reranker_model": {"show": False},
            "top_p": {"show": False},
        }

        result = component.update_build_config(build_config, field_value=True, field_name="use_embeddings")

        # Embedding fields should be visible
        assert result["embedding_model"]["show"] is True
        assert result["top_k"]["show"] is True
        assert result["similarity_threshold"]["show"] is True

        # Augmentation fields should be hidden (augment_descriptions is False)
        assert result["augmentation_model"]["show"] is False

        # Reranker fields should be hidden
        assert result["reranker_model"]["show"] is False

    def test_augmentation_with_cache(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test that augmentation uses cache when available."""
        mock_embedding = Mock()
        mock_embedding.embed_documents.return_value = [[0.1, 0.2, 0.3]] * 5

        # First call - should invoke LLM
        mock_llm_model.invoke.return_value.content = '["desc1", "desc2", "desc3", "desc4", "desc5"]'

        component = component_class(
            tools=sample_tools,
            user_query="test",
            use_embeddings=True,
            embedding_model=mock_embedding,
            augment_descriptions=True,
            augmentation_model=mock_llm_model,
            augmentation_samples=1,
            top_k=3,
            _session_id=session_id,
        )

        # Clear cache for this test
        with patch.object(component_class, "_persistent_cache", return_value={}):
            descriptions, dependencies = component._augment_tool_descriptions(
                sample_tools, mock_llm_model, "test prompt", 1
            )
            descriptions2, dependencies2 = component._augment_tool_descriptions(
                sample_tools, mock_llm_model, "test prompt", 1
            )

        assert len(descriptions) == len(sample_tools)
        assert isinstance(dependencies, dict)
        assert mock_llm_model.invoke.call_count == 1
        assert descriptions2 == descriptions
        assert dependencies2 == dependencies

    def test_component_frontend_node(self, component_class, default_kwargs):
        """Test that component generates correct frontend node."""
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Semantic Tools Filter"
        assert "semantic similarity" in node_data["description"].lower()
        assert node_data["icon"] == "filter"

    def test_reranker_fallback_on_parse_error(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test that reranker falls back to embedding ranking on parse error."""
        # Make LLM return unparseable response
        mock_llm_model.invoke.return_value.content = "This is not JSON"

        candidates = [(tool, 0.5) for tool in sample_tools[:3]]

        component = component_class(
            tools=sample_tools,
            user_query="test",
            use_reranker=True,
            reranker_model=mock_llm_model,
            top_p=2,
            _session_id=session_id,
        )

        result = component._rerank_with_llm("test query", candidates, mock_llm_model, 2)

        # Should fall back to first 2 candidates
        assert len(result) == 2
        assert result == candidates[:2]

    def test_augmentation_fallback_on_parse_error(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test that augmentation falls back to original descriptions on parse error."""
        # Make LLM return unparseable response
        mock_llm_model.invoke.return_value.content = "This is not JSON"

        component = component_class(
            tools=sample_tools,
            user_query="test",
            augment_descriptions=True,
            augmentation_model=mock_llm_model,
            _session_id=session_id,
        )

        descriptions, dependencies = component._augment_tool_descriptions(
            sample_tools, mock_llm_model, "test prompt", 1
        )

        # Should return original descriptions
        assert len(descriptions) == len(sample_tools)
        assert isinstance(dependencies, dict)
        for i, tool in enumerate(sample_tools):
            assert descriptions[i][0] == (tool.description or "")

    def test_augmentation_with_multiple_samples(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test augmentation with multiple samples per tool."""
        # Return nested array for multiple samples
        mock_llm_model.invoke.return_value.content = (
            '[["desc1a", "desc1b"], ["desc2a", "desc2b"], '
            '["desc3a", "desc3b"], ["desc4a", "desc4b"], ["desc5a", "desc5b"]]'
        )

        component = component_class(
            tools=sample_tools,
            user_query="test",
            augment_descriptions=True,
            augmentation_model=mock_llm_model,
            augmentation_samples=2,
            _session_id=session_id,
        )

        with patch.object(component_class, "_persistent_cache", return_value={}):
            descriptions, dependencies = component._augment_tool_descriptions(
                sample_tools, mock_llm_model, "test prompt", 2
            )

        assert len(descriptions) == len(sample_tools)
        assert isinstance(dependencies, dict)
        for samples in descriptions:
            assert len(samples) == 2  # Each tool should have 2 samples

    def test_dependency_detection(self, component_class, sample_tools, mock_llm_model, session_id):
        """Test that dependencies are detected and cached."""
        # Return structured response with dependencies
        mock_llm_model.invoke.return_value.content = """
        {
            "descriptions": [
                "Calculator for math operations",
                "Weather service that needs location data",
                "Web search engine",
                "Translation service",
                "Calendar management tool"
            ],
            "dependencies": [
                [],
                ["location", "geocoding", "coordinates"],
                [],
                ["language_detection"],
                ["time_zone", "location"]
            ]
        }
        """

        component = component_class(
            tools=sample_tools,
            user_query="test",
            augment_descriptions=True,
            augmentation_model=mock_llm_model,
            _session_id=session_id,
        )

        with patch.object(component_class, "_persistent_cache", return_value={}):
            descriptions, dependencies = component._augment_tool_descriptions(
                sample_tools, mock_llm_model, "test prompt", 1
            )

        # Check descriptions
        assert len(descriptions) == len(sample_tools)

        # Check dependencies (now keyed by tool index, not name)
        assert isinstance(dependencies, dict)
        # Tool indices: 0=calculator, 1=weather, 2=search, 3=translator, 4=calendar
        assert 1 in dependencies  # weather tool
        assert "location" in dependencies[1]
        assert "geocoding" in dependencies[1]
        assert 3 in dependencies  # translator tool
        assert "language_detection" in dependencies[3]
        assert 4 in dependencies  # calendar tool
        assert "location" in dependencies[4]

    def test_dependency_expansion(
        self, component_class, sample_tools, mock_embedding_model, mock_llm_model, session_id
    ):
        """Test that dependency expansion adds related tools."""
        # Mock augmentation to return dependencies
        mock_llm_model.invoke.return_value.content = """
        {
            "descriptions": [
                "Calculator for math",
                "Weather service needs location",
                "Web search",
                "Translation service",
                "Calendar tool"
            ],
            "dependencies": [
                [],
                ["location", "geocoding"],
                [],
                [],
                []
            ]
        }
        """

        # Create a location tool that should be added as dependency
        location_tool = Tool(
            name="get_location",
            description="Get user's current location coordinates",
            func=lambda x: "location",  # noqa: ARG005
        )
        all_tools = [*sample_tools, location_tool]

        component = component_class(
            tools=all_tools,
            user_query="what's the weather",
            use_embeddings=True,
            embedding_model=mock_embedding_model,
            augment_descriptions=True,
            augmentation_model=mock_llm_model,
            top_k=2,  # Only select top 2 initially
            _session_id=session_id,
        )

        # Mock embeddings to favor weather tool
        mock_embedding_model.embed_documents.return_value = [
            [0.1, 0.2, 0.3],  # calculator
            [0.9, 0.9, 0.9],  # weather (high similarity)
            [0.2, 0.3, 0.4],  # search
            [0.1, 0.2, 0.3],  # translator
            [0.1, 0.2, 0.3],  # calendar
            [0.3, 0.4, 0.5],  # location (should be added via dependency)
        ]
        mock_embedding_model.embed_query.return_value = [0.9, 0.9, 0.9]

        with patch.object(component_class, "_persistent_cache", return_value={}):
            result = component.filter_tools()

        # Weather should be selected, and location should be added via dependency expansion
        result_names = [t.name for t in result]
        assert "weather" in result_names
        # Location tool should be added because weather depends on "location"
        assert "get_location" in result_names, (
            f"Expected 'get_location' to be added via dependency expansion. Got tools: {result_names}"
        )
