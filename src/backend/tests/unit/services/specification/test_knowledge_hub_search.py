"""Tests for KnowledgeHubSearch component."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from langflow.components.knowledge_bases.knowledge_hub_search import KnowledgeHubSearchComponent
from langflow.schema import Data


class TestKnowledgeHubSearchComponent:
    """Test KnowledgeHubSearchComponent class."""

    @pytest.fixture
    def component(self):
        """Create KnowledgeHubSearchComponent instance."""
        return KnowledgeHubSearchComponent()

    @pytest.fixture
    def mock_knowledge_service(self):
        """Mock Genesis Knowledge Service."""
        service = Mock()
        service.ready = True
        service.get_knowledge_hubs = AsyncMock(return_value=[
            {"id": "hub1", "name": "Medical Knowledge"},
            {"id": "hub2", "name": "Drug Database"},
            {"id": "hub3", "name": "Clinical Guidelines"}
        ])
        service.query_vector_store = AsyncMock(return_value=[
            {
                "metadata": {
                    "content": "Sample medical content about symptoms",
                    "source": "medical_journal.pdf",
                    "score": 0.95
                }
            },
            {
                "metadata": {
                    "content": "Drug interaction information",
                    "source": "drug_database.txt",
                    "score": 0.87
                }
            }
        ])
        return service

    def test_component_initialization(self, component):
        """Test component initialization."""
        assert component.display_name == "Knowledge Hub Search"
        assert component.description == "This component is used to search for information in the knowledge hub."
        assert component.icon == "Autonomize"
        assert component.name == "KnowledgeHubSearch"

        # Test initial state
        assert component._hub_data == []
        assert component._selected_hub_names == []

    def test_component_inputs(self, component):
        """Test component inputs."""
        inputs = component.inputs
        input_names = [inp.name for inp in inputs]

        assert "search_query" in input_names
        assert "selected_hubs" in input_names
        assert "search_type" in input_names
        assert "top_k" in input_names

        # Test search_query input
        search_query_input = next(inp for inp in inputs if inp.name == "search_query")
        assert search_query_input.tool_mode is True

        # Test selected_hubs input
        selected_hubs_input = next(inp for inp in inputs if inp.name == "selected_hubs")
        assert selected_hubs_input.refresh_button is True
        assert selected_hubs_input.value == []

        # Test search_type input
        search_type_input = next(inp for inp in inputs if inp.name == "search_type")
        assert "similarity" in search_type_input.options
        assert "semantic" in search_type_input.options
        assert "keyword" in search_type_input.options
        assert "hybrid" in search_type_input.options
        assert search_type_input.value == "similarity"

        # Test top_k input
        top_k_input = next(inp for inp in inputs if inp.name == "top_k")
        assert top_k_input.value == 10

    def test_component_outputs(self, component):
        """Test component outputs."""
        outputs = component.outputs
        assert len(outputs) == 1

        output = outputs[0]
        assert output.display_name == "Query Results"
        assert output.name == "query_results"
        assert output.method == "build_output"

    @pytest.mark.asyncio
    async def test_update_build_config_success(self, component, mock_knowledge_service):
        """Test successful build config update."""
        build_config = {
            "selected_hubs": {
                "options": []
            }
        }

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.update_build_config(build_config, [], "selected_hubs")

        # Verify service was called
        mock_knowledge_service.get_knowledge_hubs.assert_called_once()

        # Verify build config was updated
        assert result["selected_hubs"]["options"] == ["Medical Knowledge", "Drug Database", "Clinical Guidelines"]

        # Verify internal state was updated
        assert len(component._hub_data) == 3
        assert component._hub_data[0]["name"] == "Medical Knowledge"

    @pytest.mark.asyncio
    async def test_update_build_config_service_not_ready(self, component):
        """Test build config update when service is not ready."""
        build_config = {
            "selected_hubs": {
                "options": []
            }
        }

        mock_service = Mock()
        mock_service.ready = False

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_service):
            result = await component.update_build_config(build_config, [], "selected_hubs")

        assert result["selected_hubs"]["options"] == ["Service not ready"]

    @pytest.mark.asyncio
    async def test_update_build_config_service_error(self, component):
        """Test build config update when service throws error."""
        build_config = {
            "selected_hubs": {
                "options": []
            }
        }

        mock_service = Mock()
        mock_service.ready = True
        mock_service.get_knowledge_hubs = AsyncMock(side_effect=Exception("Service error"))

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_service):
            with pytest.raises(Exception):
                await component.update_build_config(build_config, [], "selected_hubs")

    @pytest.mark.asyncio
    async def test_update_build_config_wrong_field(self, component):
        """Test build config update for non-selected_hubs field."""
        build_config = {"other_field": {"options": []}}

        result = await component.update_build_config(build_config, "value", "other_field")

        # Should return original config unchanged
        assert result == build_config

    @pytest.mark.asyncio
    async def test_build_output_success(self, component, mock_knowledge_service):
        """Test successful build output."""
        # Set up component state
        component._selected_hub_names = ["Medical Knowledge", "Drug Database"]
        component._hub_data = [
            {"id": "hub1", "name": "Medical Knowledge"},
            {"id": "hub2", "name": "Drug Database"}
        ]
        component.search_query = "drug interactions"

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.build_output()

        # Verify service was called with correct parameters
        mock_knowledge_service.query_vector_store.assert_called_once_with(
            knowledge_hub_ids=["hub1", "hub2"],
            query="drug interactions"
        )

        # Verify result
        assert isinstance(result, Data)
        assert "Sample medical content about symptoms" in result.text
        assert "Drug interaction information" in result.text
        assert "=== NEW CHUNK ===" in result.text

        # Verify data structure
        assert "result" in result.data
        assert "used_data_sources" in result.data
        assert result.data["used_data_sources"] == ["Medical Knowledge", "Drug Database"]

    @pytest.mark.asyncio
    async def test_build_output_no_hubs_selected(self, component):
        """Test build output when no hubs are selected."""
        component._selected_hub_names = []

        result = await component.build_output()

        assert isinstance(result, Data)
        assert result.value == {"query_results": []}

    @pytest.mark.asyncio
    async def test_build_output_service_not_ready(self, component):
        """Test build output when service is not ready."""
        component._selected_hub_names = ["Medical Knowledge"]

        mock_service = Mock()
        mock_service.ready = False

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_service):
            result = await component.build_output()

        assert isinstance(result, Data)
        assert result.value == {"query_results": []}

    @pytest.mark.asyncio
    async def test_build_output_service_error(self, component, mock_knowledge_service):
        """Test build output when service throws error."""
        component._selected_hub_names = ["Medical Knowledge"]
        component._hub_data = [{"id": "hub1", "name": "Medical Knowledge"}]
        component.search_query = "test query"

        mock_knowledge_service.query_vector_store = AsyncMock(side_effect=Exception("Query error"))

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.build_output()

        assert isinstance(result, Data)
        assert result.value == {"query_results": []}

    @pytest.mark.asyncio
    async def test_build_output_refreshes_hub_data(self, component, mock_knowledge_service):
        """Test build output refreshes hub data when needed."""
        component._selected_hub_names = ["Medical Knowledge"]
        component._hub_data = []  # Empty hub data should trigger refresh
        component.search_query = "test query"

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.build_output()

        # Should have called get_knowledge_hubs to refresh data
        mock_knowledge_service.get_knowledge_hubs.assert_called_once()

        # Hub data should be populated
        assert len(component._hub_data) == 3

    @pytest.mark.asyncio
    async def test_validate_and_refresh_data_sources(self, component, mock_knowledge_service):
        """Test validation and refresh of data sources."""
        component._selected_hub_names = ["Medical Knowledge", "Nonexistent Hub"]
        component._hub_data = []

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            is_valid, validated_hubs = await component._validate_and_refresh_data_sources()

        # Should be valid since at least one hub exists
        assert is_valid is True
        assert "Medical Knowledge" in validated_hubs
        assert "Nonexistent Hub" not in validated_hubs

    @pytest.mark.asyncio
    async def test_validate_and_refresh_data_sources_none_valid(self, component, mock_knowledge_service):
        """Test validation when no selected hubs are valid."""
        component._selected_hub_names = ["Nonexistent Hub 1", "Nonexistent Hub 2"]
        component._hub_data = []

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            is_valid, validated_hubs = await component._validate_and_refresh_data_sources()

        # Should be invalid since no hubs exist
        assert is_valid is False
        assert validated_hubs == []

    def test_search_query_property(self, component):
        """Test search_query property access."""
        # Set search query
        component.search_query = "test query"
        assert component.search_query == "test query"

        # Test with different types
        component.search_query = ""
        assert component.search_query == ""

    def test_selected_hubs_property(self, component):
        """Test selected_hubs property access."""
        # Test with list
        hubs = ["Hub 1", "Hub 2"]
        component.selected_hubs = hubs
        assert component.selected_hubs == hubs

        # Test with empty list
        component.selected_hubs = []
        assert component.selected_hubs == []

    def test_search_type_property(self, component):
        """Test search_type property access."""
        component.search_type = "semantic"
        assert component.search_type == "semantic"

        component.search_type = "hybrid"
        assert component.search_type == "hybrid"

    def test_top_k_property(self, component):
        """Test top_k property access."""
        component.top_k = 5
        assert component.top_k == 5

        component.top_k = 20
        assert component.top_k == 20

    @pytest.mark.asyncio
    async def test_concurrent_build_config_updates(self, component, mock_knowledge_service):
        """Test concurrent build config updates."""
        build_config = {"selected_hubs": {"options": []}}

        # Simulate concurrent calls
        import asyncio
        tasks = [
            component.update_build_config(build_config, [], "selected_hubs"),
            component.update_build_config(build_config, [], "selected_hubs")
        ]

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            results = await asyncio.gather(*tasks)

        # Both should succeed
        for result in results:
            assert "Medical Knowledge" in result["selected_hubs"]["options"]

    @pytest.mark.asyncio
    async def test_edge_case_empty_query_results(self, component, mock_knowledge_service):
        """Test handling of empty query results."""
        component._selected_hub_names = ["Medical Knowledge"]
        component._hub_data = [{"id": "hub1", "name": "Medical Knowledge"}]
        component.search_query = "nonexistent content"

        # Mock empty results
        mock_knowledge_service.query_vector_store = AsyncMock(return_value=[])

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.build_output()

        assert isinstance(result, Data)
        assert result.text == ""  # Empty content
        assert result.data["result"] == []

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, component, mock_knowledge_service):
        """Test handling of special characters in search query."""
        component._selected_hub_names = ["Medical Knowledge"]
        component._hub_data = [{"id": "hub1", "name": "Medical Knowledge"}]
        component.search_query = "drug & side-effects: 50% patients"

        with patch('langflow.services.deps.get_knowledge_service', return_value=mock_knowledge_service):
            result = await component.build_output()

        # Should handle special characters without errors
        mock_knowledge_service.query_vector_store.assert_called_once_with(
            knowledge_hub_ids=["hub1"],
            query="drug & side-effects: 50% patients"
        )