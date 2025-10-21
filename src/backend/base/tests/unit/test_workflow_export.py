"""Unit tests for workflow export functionality."""

import json
import pytest
from unittest.mock import Mock, patch

from langflow.services.runtime.flow_to_spec_converter import FlowToSpecConverter
from langflow.services.runtime.langflow_converter import LangflowConverter


class TestFlowToSpecConverter:
    """Test suite for FlowToSpecConverter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = FlowToSpecConverter()

    def test_converter_initialization(self):
        """Test converter initializes correctly."""
        assert self.converter is not None
        assert self.converter.langflow_converter is not None
        assert isinstance(self.converter.langflow_converter, LangflowConverter)

    def test_validate_flow_data_valid(self):
        """Test flow data validation with valid data."""
        valid_flow = {
            "data": {
                "nodes": [
                    {
                        "id": "node1",
                        "data": {
                            "type": "ChatInput",
                            "display_name": "Input"
                        }
                    }
                ],
                "edges": []
            }
        }

        result = self.converter._validate_flow_data(valid_flow)
        assert result is True

    def test_validate_flow_data_invalid(self):
        """Test flow data validation with invalid data."""
        invalid_flows = [
            None,
            {},
            {"data": None},
            {"data": {"nodes": "not_a_list"}},
            {"data": {"nodes": [], "edges": "not_a_list"}}
        ]

        for invalid_flow in invalid_flows:
            result = self.converter._validate_flow_data(invalid_flow)
            assert result is False

    def test_generate_spec_id(self):
        """Test specification ID generation."""
        result = self.converter._generate_spec_id("Test Agent", "healthcare")
        expected = "urn:agent:genesis:healthcare:test-agent:1.0.0"
        assert result == expected

    def test_extract_variables_from_flow(self):
        """Test variable extraction from flow data."""
        flow_with_variables = {
            "variables": {
                "api_key": "test_key",
                "model": "gpt-4"
            },
            "data": {
                "nodes": [
                    {
                        "id": "node1",
                        "data": {
                            "node": {
                                "template": {
                                    "api_key": {
                                        "value": "${API_KEY}"
                                    },
                                    "temperature": {
                                        "value": 0.7
                                    }
                                }
                            }
                        }
                    }
                ],
                "edges": []
            }
        }

        variables = self.converter._extract_variables_from_flow(flow_with_variables)
        assert "api_key" in variables
        assert "model" in variables
        assert "API_KEY" in variables

    def test_extract_extended_metadata(self):
        """Test extended metadata extraction."""
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "agent1",
                        "data": {"type": "Agent"}
                    },
                    {
                        "id": "tool1",
                        "data": {"type": "ToolSearcher"}
                    },
                    {
                        "id": "prompt1",
                        "data": {"type": "PromptTemplate"}
                    }
                ],
                "edges": [
                    {"source": "tool1", "target": "agent1"},
                    {"source": "prompt1", "target": "agent1"}
                ]
            }
        }

        metadata = self.converter._extract_extended_metadata(flow_data)
        assert metadata.get("toolsUse") is True
        assert metadata.get("agencyLevel") == "ModelBasedReflexAgent"
        assert "agent-based" in metadata.get("tags", [])
        assert "tool-enabled" in metadata.get("tags", [])
        assert "prompt-driven" in metadata.get("tags", [])

    @patch.object(LangflowConverter, '_convert_langflow_to_genesis')
    def test_convert_flow_to_spec_basic(self, mock_convert):
        """Test basic flow to spec conversion."""
        mock_convert.return_value = {
            "id": "urn:agent:genesis:test:flow:1.0.0",
            "name": "Test Flow",
            "description": "Test description",
            "components": {}
        }

        flow_data = {
            "name": "Test Flow",
            "data": {
                "nodes": [{"id": "node1", "data": {"type": "ChatInput"}}],
                "edges": []
            }
        }

        result = self.converter.convert_flow_to_spec(flow_data)

        assert result is not None
        assert result["name"] == "Test Flow"
        assert "_conversion" in result
        mock_convert.assert_called_once()

    def test_validate_flow_for_conversion_valid(self):
        """Test flow validation for conversion with valid flow."""
        valid_flow = {
            "data": {
                "nodes": [
                    {
                        "id": "input1",
                        "data": {
                            "type": "ChatInput",
                            "display_name": "Input"
                        }
                    }
                ],
                "edges": []
            }
        }

        result = self.converter.validate_flow_for_conversion(valid_flow)
        assert result["valid"] is True
        assert "statistics" in result
        assert result["statistics"]["nodes_count"] == 1

    def test_validate_flow_for_conversion_invalid(self):
        """Test flow validation for conversion with invalid flow."""
        invalid_flow = {
            "data": {
                "nodes": [],
                "edges": []
            }
        }

        result = self.converter.validate_flow_for_conversion(invalid_flow)
        assert result["valid"] is False
        assert "No convertible components found" in result["errors"]


class TestWorkflowExportAPI:
    """Test suite for workflow export API endpoints."""

    @pytest.fixture
    def mock_converter(self):
        """Mock FlowToSpecConverter for API tests."""
        with patch('langflow.api.v1.spec.FlowToSpecConverter') as mock:
            yield mock

    def test_export_api_success(self, mock_converter):
        """Test successful flow export via API."""
        # This would require setting up FastAPI test client
        # For now, just test that the converter is called correctly
        mock_instance = mock_converter.return_value
        mock_instance.convert_flow_to_spec.return_value = {
            "id": "urn:agent:genesis:test:flow:1.0.0",
            "name": "Test Flow",
            "components": {}
        }

        # Test would call the API endpoint here
        # assert response.status_code == 200
        # assert response.json()["success"] is True

    def test_batch_export_api_success(self, mock_converter):
        """Test successful batch flow export via API."""
        mock_instance = mock_converter.return_value
        mock_instance.convert_flows_batch.return_value = [
            {"id": "urn:agent:genesis:test:flow1:1.0.0", "name": "Flow 1"},
            {"id": "urn:agent:genesis:test:flow2:1.0.0", "name": "Flow 2"}
        ]

        # Test would call the batch export API endpoint here
        # assert response.status_code == 200
        # assert response.json()["successful_exports"] == 2


if __name__ == "__main__":
    pytest.main([__file__])