from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from langflow.components.nvidia.nemo_guardrails import (
    GuardrailsConfigInput,
    NVIDIANeMoGuardrailsComponent,
)
from langflow.schema.message import Message


@pytest.fixture
async def component():
    """Create a test instance of the NeMo Guardrails component."""
    from tests.base import ComponentTestBase

    # Use the proper component setup method
    test_base = ComponentTestBase()
    return await test_base.component_setup(
        NVIDIANeMoGuardrailsComponent,
        {
            "base_url": "https://test.api.nvidia.com/nemo",
            "auth_token": "test_token",
            "namespace": "test_namespace",
            "config": "test_config",
            "validation_mode": "input",
        },
    )


class TestGuardrailsConfigInput:
    """Test the GuardrailsConfigInput dataclass."""

    def test_guardrails_config_input_structure(self):
        """Test that GuardrailsConfigInput has the correct structure."""
        config_input = GuardrailsConfigInput()

        assert config_input.functionality == "create"
        assert "data" in config_input.fields
        assert "node" in config_input.fields["data"]
        assert config_input.fields["data"]["node"]["name"] == "create_guardrails_config"
        assert "template" in config_input.fields["data"]["node"]


class TestNVIDIANeMoGuardrailsComponent:
    """Test the NVIDIANeMoGuardrailsComponent class."""

    def test_init(self, component):
        """Test component initialization."""
        assert component.display_name == "NeMo Guardrails"
        assert component.name == "NVIDIANemoGuardrails"
        assert component.beta is True

    def test_get_auth_headers_with_token(self, component):
        """Test authentication headers with token."""
        headers = component.get_auth_headers()

        assert headers["accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test_token"

    def test_get_auth_headers_without_token(self):
        """Test authentication headers without token."""
        component = NVIDIANeMoGuardrailsComponent()
        headers = component.get_auth_headers()

        assert headers["accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_get_nemo_client(self, component):
        """Test NeMo client creation."""
        client = component.get_nemo_client()

        assert client is not None
        # Note: We can't easily test the client type without importing it in the test

    @pytest.mark.asyncio
    async def test_fetch_guardrails_configs_success(self, component):
        """Test successful guardrails config fetching."""
        mock_config = Mock()
        mock_config.name = "test_config"
        mock_config.description = "Test guardrails configuration"
        mock_config.created = "2024-01-01T00:00:00Z"
        mock_config.updated = "2024-01-01T00:00:00Z"

        mock_response = Mock()
        mock_response.data = [mock_config]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.configs.list = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            configs, metadata = await component.fetch_guardrails_configs()

            assert configs == ["test_config"]
            assert len(metadata) == 1
            assert metadata[0]["icon"] == "Settings"
            assert metadata[0]["description"] == "Test guardrails configuration"

    @pytest.mark.asyncio
    async def test_fetch_guardrails_configs_empty(self, component):
        """Test guardrails config fetching with empty response."""
        mock_response = Mock()
        mock_response.data = []

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.configs.list = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            configs, metadata = await component.fetch_guardrails_configs()

            assert configs == []
            assert metadata == []

    @pytest.mark.asyncio
    async def test_fetch_guardrails_configs_error(self, component):
        """Test guardrails config fetching with error."""
        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.configs.list = AsyncMock(side_effect=httpx.RequestError("API Error"))
            mock_get_client.return_value = mock_client

            # This should catch the exception and return empty lists
            configs, metadata = await component.fetch_guardrails_configs()

            assert configs == []
            assert metadata == []

    @pytest.mark.asyncio
    async def test_create_guardrails_config_success(self, component):
        """Test successful config creation."""
        config_data = {
            "01_config_name": "test_config",
            "02_config_description": "Test description",
            "03_rail_types": ["content_safety_input"],
            "04_content_safety_prompt": "Test prompt",
        }

        # Create mock response with name attribute
        mock_response = Mock()
        mock_response.name = "config_123"

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.guardrail.configs.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            config_id = await component.create_guardrails_config(config_data)

            assert config_id == "config_123"

    @pytest.mark.asyncio
    async def test_create_guardrails_config_missing_name(self, component):
        """Test config creation with missing name."""
        config_data = {"03_rail_types": ["content_safety_input"]}

        with pytest.raises(ValueError, match="Config name is required"):
            await component.create_guardrails_config(config_data)

    def test_build_guardrails_params_content_safety(self, component):
        """Test parameter building for content safety rails."""
        config_data = {"04_content_safety_prompt": "Custom safety prompt"}
        rail_types = ["content_safety_input", "content_safety_output"]

        params = component._build_guardrails_params(config_data, rail_types)

        assert "content safety check input" in params["rails"]["input"]["flows"]
        assert "content safety check output" in params["rails"]["output"]["flows"]
        assert len(params["prompts"]) == 2
        assert params["prompts"][0]["content"] == "Custom safety prompt"

    def test_build_guardrails_params_topic_control(self, component):
        """Test parameter building for topic control rails."""
        config_data = {"05_topic_control_prompt": "Custom topic prompt"}
        rail_types = ["topic_control"]

        params = component._build_guardrails_params(config_data, rail_types)

        assert "topic safety check input" in params["rails"]["input"]["flows"]
        assert len(params["prompts"]) == 1
        assert params["prompts"][0]["content"] == "Custom topic prompt"

    def test_build_guardrails_params_self_check(self, component):
        """Test parameter building for self-check rails."""
        config_data = {"06_self_check_prompt": "Custom self-check prompt"}
        rail_types = ["self_check_input", "self_check_output", "self_check_hallucination"]

        params = component._build_guardrails_params(config_data, rail_types)

        assert "self check input" in params["rails"]["input"]["flows"]
        assert "self check output" in params["rails"]["output"]["flows"]
        assert "self check hallucination" in params["rails"]["output"]["flows"]
        assert len(params["prompts"]) == 3

    def test_build_guardrails_params_jailbreak_detection(self, component):
        """Test parameter building for jailbreak detection."""
        config_data = {}
        rail_types = ["jailbreak_detection"]

        params = component._build_guardrails_params(config_data, rail_types)

        assert "jailbreak detection heuristics" in params["rails"]["input"]["flows"]
        assert len(params["prompts"]) == 0

    @pytest.mark.asyncio
    async def test_update_build_config_guardrails_config(self, component):
        """Test build config update for guardrails config field."""
        build_config = {
            "config": {"options": [], "options_metadata": []},
        }

        with patch.object(component, "fetch_guardrails_configs", new_callable=AsyncMock) as mock_fetch_configs:
            mock_fetch_configs.return_value = (["config1", "config2"], [{"icon": "Shield"}, {"icon": "Shield"}])

            await component.update_build_config(build_config, "config1", "config")

            assert build_config["config"]["options"] == ["config1", "config2"]

    @pytest.mark.asyncio
    async def test_fetch_guardrails_configs_metadata_structure(self, component):
        """Test that guardrails config metadata has the correct structure for hover text."""
        mock_config = Mock()
        mock_config.name = "test_config"
        mock_config.description = "A comprehensive guardrails configuration for content safety"
        mock_config.created = "2024-01-01T00:00:00Z"
        mock_config.updated = "2024-01-02T00:00:00Z"

        mock_response = Mock()
        mock_response.data = [mock_config]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.configs.list = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            configs, metadata = await component.fetch_guardrails_configs()

            assert configs == ["test_config"]
            assert len(metadata) == 1

            # Verify metadata structure for hover text
            config_metadata = metadata[0]
            assert "icon" in config_metadata
            assert config_metadata["icon"] == "Settings"
            assert "description" in config_metadata
            assert config_metadata["description"] == "A comprehensive guardrails configuration for content safety"
            assert "created" in config_metadata
            assert config_metadata["created"] == "2024-01-01T00:00:00Z"
            assert "updated" in config_metadata
            assert config_metadata["updated"] == "2024-01-02T00:00:00Z"

            # Verify that description is not empty and provides meaningful information
            assert len(config_metadata["description"]) > 0
            assert config_metadata["description"] != "Guardrails configuration"  # Should use actual description

    @pytest.mark.asyncio
    async def test_fetch_guardrails_configs_empty_description(self, component):
        """Test fetching configs with empty description."""
        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # Mock response with empty description
            mock_response = Mock()
            mock_response.data = [Mock(name="test-config", description="", created=None, updated=None)]
            mock_client.guardrail.configs.list.return_value = mock_response

            configs, metadata = await component.fetch_guardrails_configs()

            assert configs == ["test-config"]
            assert len(metadata) == 1
            assert metadata[0]["description"] == "Guardrails configuration"

    @pytest.mark.asyncio
    async def test_passed_output_success(self, component):
        """Test passed_output returns validated message when guardrails pass."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            assert result.text == "Test input"
            assert result.error is False
            assert result.category == "message"

    @pytest.mark.asyncio
    async def test_passed_output_blocked(self, component):
        """Test passed_output returns empty message when guardrails block."""
        component.validation_mode = "input"
        component.input_value = "Blocked input"
        component.config = "test_config"

        # Mock the guardrail.check response for blocked validation
        mock_response = Mock()
        mock_response.status = "blocked"  # Primary method

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            # Should return empty message when blocked
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_passed_output_success_input_mode(self, component):
        """Test passed_output with successful input validation."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            assert result.text == "Test input"
            assert result.error is False
            assert result.category == "message"
            assert component.status == "Input validated successfully"

            # Verify the guardrail.check was called with correct parameters
            mock_client.guardrail.check.assert_called_once_with(
                messages=[{"role": "user", "content": "Test input"}],
                model="nvidia/llama-3.1-8b-instruct",
                guardrails={"config_id": "test_config"},
                extra_headers=component.get_auth_headers(),
            )

    @pytest.mark.asyncio
    async def test_passed_output_success_output_mode(self, component):
        """Test passed_output with successful output validation."""
        component.validation_mode = "output"
        component.input_value = "Test output"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            assert result.text == "Test output"
            assert result.error is False
            assert result.category == "message"
            assert component.status == "Output validated successfully"

            # Verify the guardrail.check was called with correct parameters
            mock_client.guardrail.check.assert_called_once_with(
                messages=[{"role": "assistant", "content": "Test output"}],
                model="nvidia/llama-3.1-8b-instruct",
                guardrails={"config_id": "test_config"},
                extra_headers=component.get_auth_headers(),
            )

    @pytest.mark.asyncio
    async def test_blocked_output_blocked_input_mode(self, component):
        """Test blocked_output with blocked input validation."""
        component.validation_mode = "input"
        component.input_value = "Blocked input"
        component.config = "test_config"

        # Mock the guardrail.check response for blocked validation
        mock_response = Mock()
        mock_response.status = "blocked"  # Primary method

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"
            assert component.status == "Input blocked by guardrails"
            # Verify content_blocks are present
            assert result.content_blocks is not None
            assert len(result.content_blocks) > 0

    @pytest.mark.asyncio
    async def test_blocked_output_blocked_output_mode(self, component):
        """Test blocked_output with blocked output validation."""
        component.validation_mode = "output"
        component.input_value = "Blocked output"
        component.config = "test_config"

        # Mock the guardrail.check response for blocked validation
        mock_response = Mock()
        mock_response.status = "blocked"  # Primary method

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            assert result.text == "I cannot process that output."
            assert result.error is True
            assert result.category == "error"
            assert component.status == "Output blocked by guardrails"
            # Verify content_blocks are present
            assert result.content_blocks is not None
            assert len(result.content_blocks) > 0

    @pytest.mark.asyncio
    async def test_blocked_output_fallback_blocked_field(self, component):
        """Test blocked_output with fallback blocked field when status not available."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response with blocked field (fallback)
        mock_response = Mock()
        mock_response.status = None  # Simulate missing status field
        mock_response.blocked = True  # Fallback to blocked field

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"
            assert component.status == "Input blocked by guardrails"

    @pytest.mark.asyncio
    async def test_blocked_output_fallback_choices_format(self, component):
        """Test blocked_output with fallback choices format when status/blocked not available."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response with choices format (fallback)
        mock_choice = Mock()
        mock_choice.finish_reason = "guardrail_blocked"
        mock_response = Mock()
        mock_response.status = None  # Simulate missing status field
        mock_response.blocked = None  # Simulate missing blocked field
        mock_response.choices = [mock_choice]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"
            assert component.status == "Input blocked by guardrails"

    @pytest.mark.asyncio
    async def test_blocked_output_passed_validation(self, component):
        """Test blocked_output returns empty message when validation passes."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            # Should return empty message when validation passes
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_blocked_output_rails_status_blocked(self, component):
        """Test blocked_output with rails_status indicating blocked."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response with rails_status indicating blocked
        mock_rail_status = Mock()
        mock_rail_status.status = "blocked"
        mock_response = Mock()
        mock_response.status = None  # No top-level status
        mock_response.rails_status = {"content_safety": mock_rail_status}

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.blocked_output()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"

    @pytest.mark.asyncio
    async def test_validation_empty_input(self, component):
        """Test validation with empty input."""
        component.validation_mode = "input"
        component.input_value = ""
        component.system_message = ""
        component.config = "test_config"

        with pytest.raises(ValueError, match="The message you want to validate is empty"):
            await component.passed_output()

    @pytest.mark.asyncio
    async def test_passed_output_with_system_message(self, component):
        """Test passed_output with system message included."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.system_message = "System instruction"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            # Should include system message in the validated text
            assert "System instruction" in result.text
            assert "Test input" in result.text

    @pytest.mark.asyncio
    async def test_passed_output_with_message_object(self, component):
        """Test passed_output with Message object input."""
        component.validation_mode = "input"
        component.input_value = Message(text="Test message")
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.status = "allowed"  # Primary method
        mock_response.blocked = False

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.passed_output()

            assert result.text == "Test message"
            assert result.error is False

    @pytest.mark.asyncio
    async def test_validation_api_error(self, component):
        """Test validation with API error."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="API Error"):
                await component.passed_output()

    @pytest.mark.asyncio
    async def test_validation_http_error_with_response(self, component):
        """Test validation with HTTP error that has response details."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Create a mock exception with response details
        mock_exception = Exception("HTTP Error")
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_exception.response = mock_response

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(side_effect=mock_exception)
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="HTTP Error"):
                await component.passed_output()

    @pytest.mark.asyncio
    async def test_validation_nemo_exception_message(self, component):
        """Test validation with NeMo exception that has a message."""
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Create a mock exception with body message
        mock_exception = Exception("NeMo Error")
        mock_exception.body = {"message": "Guardrails configuration not found"}

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(side_effect=mock_exception)
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError, match="Guardrails configuration not found"):
                await component.passed_output()
