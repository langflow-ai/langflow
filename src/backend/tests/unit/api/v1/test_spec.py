"""Tests for spec API endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from langflow.api.v1.spec import router


class TestSpecAPI:
    """Test spec API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_knowledge_endpoint_no_auth_required(self, client):
        """Test that knowledge endpoint doesn't require authentication."""
        with patch('langflow.api.v1.spec.ComponentMapper') as MockMapper:
            # Setup mock
            mock_mapper = MockMapper.return_value
            mock_mapper.AUTONOMIZE_MODELS = {
                "genesis:rxnorm": {"component": "AutonomizeModel", "config": {"selected_model": "RxNorm Code"}}
            }
            mock_mapper.MCP_MAPPINGS = {
                "genesis:mcp_tool": {"component": "MCPTools", "config": {}}
            }
            mock_mapper.STANDARD_MAPPINGS = {
                "genesis:agent": {"component": "Agent", "config": {}}
            }
            mock_mapper.is_tool_component = Mock(return_value=False)

            # Test without any auth headers
            response = client.post(
                "/knowledge",
                json={"query_type": "components", "reload_cache": False}
            )

            # Should succeed without authentication
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "components" in data["knowledge"]
            assert len(data["knowledge"]["components"]) == 3

    def test_knowledge_endpoint_components(self, client):
        """Test knowledge endpoint returns components correctly."""
        with patch('langflow.api.v1.spec.ComponentMapper') as MockMapper:
            mock_mapper = MockMapper.return_value
            mock_mapper.AUTONOMIZE_MODELS = {
                "genesis:clinical_llm": {"component": "AutonomizeModel", "config": {"selected_model": "Clinical LLM"}}
            }
            mock_mapper.MCP_MAPPINGS = {}
            mock_mapper.STANDARD_MAPPINGS = {
                "genesis:chat_input": {"component": "ChatInput", "config": {}},
                "genesis:chat_output": {"component": "ChatOutput", "config": {}}
            }
            mock_mapper.is_tool_component = Mock(side_effect=lambda x: x == "genesis:mcp_tool")

            response = client.post(
                "/knowledge",
                json={"query_type": "components", "reload_cache": False}
            )

            assert response.status_code == 200
            data = response.json()
            components = data["knowledge"]["components"]

            # Verify component structure
            assert "genesis:clinical_llm" in components
            assert components["genesis:clinical_llm"]["component"] == "AutonomizeModel"
            assert components["genesis:clinical_llm"]["is_tool"] is False

            assert "genesis:chat_input" in components
            assert components["genesis:chat_input"]["component"] == "ChatInput"

    def test_knowledge_endpoint_patterns(self, client):
        """Test knowledge endpoint can load patterns."""
        with patch('langflow.api.v1.spec.Path') as MockPath:
            # Mock pattern file exists
            mock_file = Mock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = """
            ## Simple Linear Agent Pattern
            Description here

            ## Multi-Tool Agent Pattern
            Another pattern
            """
            MockPath.return_value.parent.parent.parent = Mock()
            MockPath.return_value.parent.parent.parent.__truediv__ = Mock(return_value=Mock(__truediv__=Mock(return_value=Mock(__truediv__=Mock(return_value=Mock(__truediv__=Mock(return_value=mock_file)))))))

            response = client.post(
                "/knowledge",
                json={"query_type": "patterns", "reload_cache": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert "patterns" in data["knowledge"]

    def test_knowledge_endpoint_all(self, client):
        """Test knowledge endpoint returns all types."""
        with patch('langflow.api.v1.spec.ComponentMapper') as MockMapper, \
             patch('langflow.api.v1.spec.Path') as MockPath:

            # Setup component mapper
            mock_mapper = MockMapper.return_value
            mock_mapper.AUTONOMIZE_MODELS = {"genesis:rxnorm": {"component": "AutonomizeModel", "config": {}}}
            mock_mapper.MCP_MAPPINGS = {}
            mock_mapper.STANDARD_MAPPINGS = {}
            mock_mapper.is_tool_component = Mock(return_value=False)

            # Setup path for patterns
            MockPath.return_value.parent.parent.parent = Mock()

            response = client.post(
                "/knowledge",
                json={"query_type": "all", "reload_cache": False}
            )

            assert response.status_code == 200
            data = response.json()
            knowledge = data["knowledge"]

            # Should have all three types
            assert "components" in knowledge
            assert "patterns" in knowledge
            assert "specifications" in knowledge

    def test_validate_endpoint_no_auth(self, client):
        """Test validate endpoint works without authentication."""
        with patch('langflow.services.spec.service.SpecService') as MockService:
            mock_service = MockService.return_value
            mock_service.validate_spec.return_value = {
                "valid": True,
                "errors": [],
                "warnings": []
            }

            response = client.post(
                "/validate",
                json={"spec_yaml": "test: yaml"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True

    def test_convert_endpoint_no_auth(self, client):
        """Test convert endpoint works without authentication."""
        with patch('langflow.services.spec.service.SpecService') as MockService:
            mock_service = MockService.return_value
            mock_service.convert_spec_to_flow = Mock(return_value={"flow": "data"})

            response = client.post(
                "/convert",
                json={"spec_yaml": "test: yaml", "variables": None, "tweaks": None}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "flow" in data

    def test_components_endpoint_no_auth(self, client):
        """Test components endpoint works without authentication."""
        with patch('langflow.services.spec.service.SpecService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_available_components.return_value = {
                "genesis:agent": {"name": "Agent", "description": "Agent component"}
            }

            response = client.get("/components")

            assert response.status_code == 200
            data = response.json()
            assert "components" in data
            assert "genesis:agent" in data["components"]

    def test_knowledge_endpoint_error_handling(self, client):
        """Test knowledge endpoint error handling."""
        with patch('langflow.api.v1.spec.ComponentMapper') as MockMapper:
            MockMapper.side_effect = Exception("Test error")

            response = client.post(
                "/knowledge",
                json={"query_type": "components", "reload_cache": False}
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Internal server error" in data["detail"]