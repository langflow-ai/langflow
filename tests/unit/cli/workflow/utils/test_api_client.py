"""Unit tests for the APIClient class."""

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx

from langflow.cli.workflow.utils.api_client import APIClient


class TestAPIClient:
    """Test the APIClient class."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_config_manager = Mock()
        self.mock_config = Mock()
        self.mock_config.ai_studio.url = "http://localhost:7860"
        self.mock_config.ai_studio.api_key = "test-api-key"
        self.mock_config_manager.get_config.return_value = self.mock_config

        self.api_client = APIClient(self.mock_config_manager)

    def test_init(self):
        """Test APIClient initialization."""
        assert self.api_client.base_url == "http://localhost:7860"
        assert self.api_client.api_key == "test-api-key"

    def test_init_url_with_trailing_slash(self):
        """Test APIClient initialization with trailing slash in URL."""
        self.mock_config.ai_studio.url = "http://localhost:7860/"
        api_client = APIClient(self.mock_config_manager)
        assert api_client.base_url == "http://localhost:7860"

    def test_get_headers_with_api_key(self):
        """Test _get_headers with API key."""
        headers = self.api_client._get_headers()
        expected_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer test-api-key"
        }
        assert headers == expected_headers

    def test_get_headers_without_api_key(self):
        """Test _get_headers without API key."""
        self.api_client.api_key = None
        headers = self.api_client._get_headers()
        expected_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        assert headers == expected_headers

    @pytest.mark.asyncio
    async def test_validate_spec(self):
        """Test validate_spec async method."""
        spec_yaml = "name: Test Spec"
        expected_response = {"valid": True, "errors": []}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.validate_spec(spec_yaml)

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/validate",
                json={
                    "spec_yaml": spec_yaml,
                    "detailed": True,
                    "format_report": True
                },
                headers=self.api_client._get_headers(),
                timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_validate_spec_with_options(self):
        """Test validate_spec with detailed=False."""
        spec_yaml = "name: Test Spec"
        expected_response = {"valid": True, "errors": []}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.validate_spec(spec_yaml, detailed=False)

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/validate",
                json={
                    "spec_yaml": spec_yaml,
                    "detailed": False,
                    "format_report": True
                },
                headers=self.api_client._get_headers(),
                timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_convert_spec(self):
        """Test convert_spec async method."""
        spec_yaml = "name: Test Spec"
        variables = {"var1": "value1"}
        tweaks = {"component.field": "value"}
        expected_response = {"flow": {"nodes": [], "edges": []}}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.convert_spec(spec_yaml, variables, tweaks)

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/convert",
                json={
                    "spec_yaml": spec_yaml,
                    "variables": variables,
                    "tweaks": tweaks
                },
                headers=self.api_client._get_headers(),
                timeout=60.0
            )

    @pytest.mark.asyncio
    async def test_convert_spec_minimal(self):
        """Test convert_spec with minimal parameters."""
        spec_yaml = "name: Test Spec"
        expected_response = {"flow": {"nodes": [], "edges": []}}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.convert_spec(spec_yaml)

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/convert",
                json={"spec_yaml": spec_yaml},
                headers=self.api_client._get_headers(),
                timeout=60.0
            )

    @pytest.mark.asyncio
    async def test_get_available_components(self):
        """Test get_available_components async method."""
        expected_response = {"components": {"genesis:agent": {}}}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.get.return_value = mock_response

            result = await self.api_client.get_available_components()

            assert result == expected_response
            mock_client.get.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/components",
                headers=self.api_client._get_headers(),
                timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health_check async method with success."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            result = await self.api_client.health_check()

            assert result is True
            mock_client.get.assert_called_once_with(
                "http://localhost:7860/health",
                timeout=10.0
            )

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health_check async method with failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response

            result = await self.api_client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health_check async method with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection error")

            result = await self.api_client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_export_flow(self):
        """Test export_flow async method."""
        flow_data = {"nodes": [], "edges": []}
        expected_response = {"specification": {"name": "Test"}}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.export_flow(
                flow_data=flow_data,
                preserve_variables=True,
                include_metadata=True,
                name_override="Custom Name",
                description_override="Custom Description",
                domain_override="custom"
            )

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/export",
                json={
                    "flow_data": flow_data,
                    "preserve_variables": True,
                    "include_metadata": True,
                    "name_override": "Custom Name",
                    "description_override": "Custom Description",
                    "domain_override": "custom"
                },
                headers=self.api_client._get_headers(),
                timeout=60.0
            )

    @pytest.mark.asyncio
    async def test_export_flows_batch(self):
        """Test export_flows_batch async method."""
        flows = [{"nodes": [], "edges": []}]
        expected_response = {"specifications": []}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.export_flows_batch(
                flows=flows,
                preserve_variables=False,
                include_metadata=False,
                domain_override="batch"
            )

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/spec/export-batch",
                json={
                    "flows": flows,
                    "preserve_variables": False,
                    "include_metadata": False,
                    "domain_override": "batch"
                },
                headers=self.api_client._get_headers(),
                timeout=120.0
            )

    @pytest.mark.asyncio
    async def test_create_flow(self):
        """Test create_flow async method."""
        name = "Test Flow"
        data = {"nodes": [], "edges": []}
        description = "Test description"
        folder_id = "folder-123"
        expected_response = {"id": "flow-123"}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.post.return_value = mock_response

            result = await self.api_client.create_flow(name, data, description, folder_id)

            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:7860/api/v1/flows/",
                json={
                    "name": name,
                    "description": description,
                    "data": data,
                    "folder_id": folder_id
                },
                headers=self.api_client._get_headers(),
                timeout=60.0
            )

    @pytest.mark.asyncio
    async def test_get_flows(self):
        """Test get_flows async method."""
        expected_response = {"flows": []}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = expected_response
            mock_client.get.return_value = mock_response

            result = await self.api_client.get_flows()

            assert result == expected_response
            mock_client.get.assert_called_once_with(
                "http://localhost:7860/api/v1/flows/",
                headers=self.api_client._get_headers(),
                timeout=30.0
            )

    def test_validate_spec_sync(self):
        """Test synchronous wrapper for validate_spec."""
        spec_yaml = "name: Test Spec"
        expected_response = {"valid": True}

        with patch.object(self.api_client, 'validate_spec') as mock_validate:
            mock_validate.return_value = asyncio.Future()
            mock_validate.return_value.set_result(expected_response)

            with patch('asyncio.run') as mock_run:
                mock_run.return_value = expected_response

                result = self.api_client.validate_spec_sync(spec_yaml)

                assert result == expected_response
                mock_run.assert_called_once()

    def test_convert_spec_sync(self):
        """Test synchronous wrapper for convert_spec."""
        spec_yaml = "name: Test Spec"
        expected_response = {"flow": {}}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.convert_spec_sync(spec_yaml)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_get_available_components_sync(self):
        """Test synchronous wrapper for get_available_components."""
        expected_response = {"components": {}}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.get_available_components_sync()

            assert result == expected_response
            mock_run.assert_called_once()

    def test_health_check_sync(self):
        """Test synchronous wrapper for health_check."""
        expected_response = True

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.health_check_sync()

            assert result == expected_response
            mock_run.assert_called_once()

    def test_export_flow_sync(self):
        """Test synchronous wrapper for export_flow."""
        flow_data = {"nodes": [], "edges": []}
        expected_response = {"specification": {}}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.export_flow_sync(flow_data)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_create_flow_sync(self):
        """Test synchronous wrapper for create_flow."""
        name = "Test Flow"
        data = {"nodes": [], "edges": []}
        expected_response = {"id": "flow-123"}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.create_flow_sync(name, data)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_get_flows_sync(self):
        """Test synchronous wrapper for get_flows."""
        expected_response = {"flows": []}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.get_flows_sync()

            assert result == expected_response
            mock_run.assert_called_once()

    def test_delete_flow_sync(self):
        """Test synchronous wrapper for delete_flow."""
        flow_id = "flow-123"
        expected_response = {"success": True}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.delete_flow_sync(flow_id)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_get_folders_sync(self):
        """Test synchronous wrapper for get_folders."""
        expected_response = {"folders": []}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.get_folders_sync()

            assert result == expected_response
            mock_run.assert_called_once()

    def test_list_available_specifications_sync(self):
        """Test synchronous wrapper for list_available_specifications."""
        expected_response = {"specifications": []}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.list_available_specifications_sync()

            assert result == expected_response
            mock_run.assert_called_once()

    def test_create_flow_from_library_sync(self):
        """Test synchronous wrapper for create_flow_from_library."""
        specification_file = "healthcare/agent.yaml"
        folder_id = "folder-123"
        expected_response = {"flow_id": "flow-123"}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.create_flow_from_library_sync(specification_file, folder_id)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_get_component_mapping_sync(self):
        """Test synchronous wrapper for get_component_mapping."""
        spec_type = "agent"
        expected_response = {"mappings": {}}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.get_component_mapping_sync(spec_type)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_export_flows_batch_sync(self):
        """Test synchronous wrapper for export_flows_batch."""
        flows = [{"nodes": [], "edges": []}]
        expected_response = {"specifications": []}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.export_flows_batch_sync(flows)

            assert result == expected_response
            mock_run.assert_called_once()

    def test_validate_flow_for_export_sync(self):
        """Test synchronous wrapper for validate_flow_for_export."""
        flow_data = {"nodes": [], "edges": []}
        expected_response = {"valid": True}

        with patch('asyncio.run') as mock_run:
            mock_run.return_value = expected_response

            result = self.api_client.validate_flow_for_export_sync(flow_data)

            assert result == expected_response
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling with HTTP errors."""
        spec_yaml = "name: Test Spec"

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock HTTP error
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=Mock()
            )
            mock_client.post.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await self.api_client.validate_spec(spec_yaml)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in API calls."""
        spec_yaml = "name: Test Spec"

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock timeout error
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(httpx.TimeoutException):
                await self.api_client.validate_spec(spec_yaml)