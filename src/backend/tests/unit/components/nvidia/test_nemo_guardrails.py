from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from langflow.components.nvidia.nemo_guardrails import (
    GuardrailsConfigInput,
    GuardrailsMicroserviceModel,
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
            "model": "test_model",
        },
    )


@pytest.fixture
def microservice_model():
    """Create a test instance of the GuardrailsMicroserviceModel."""
    return GuardrailsMicroserviceModel(
        base_url="https://test.api.nvidia.com/nemo",
        auth_token="test_token",  # noqa: S106
        config_id="test_config",
        model_name="test_model",
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


class TestGuardrailsMicroserviceModel:
    """Test the GuardrailsMicroserviceModel class."""

    @pytest.mark.asyncio
    async def test_init(self, microservice_model):
        """Test model initialization."""
        assert microservice_model.base_url == "https://test.api.nvidia.com/nemo"
        assert microservice_model.auth_token == "test_token"  # noqa: S105
        assert microservice_model.config_id == "test_config"
        assert microservice_model.model_name == "test_model"
        assert microservice_model.stream is False

    def test_get_auth_headers(self, microservice_model):
        """Test authentication headers generation."""
        headers = microservice_model.get_auth_headers()

        assert headers["accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_invoke_non_streaming(self, microservice_model):
        """Test non-streaming invocation."""
        mock_response = Mock()
        mock_response.content = "Test response"

        with patch.object(
            microservice_model.client.guardrail.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await microservice_model.invoke({"messages": [{"role": "user", "content": "test"}]})

            mock_create.assert_called_once()
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_invoke_streaming(self, microservice_model):
        """Test streaming invocation."""
        microservice_model.stream = True
        mock_response = {"choices": [{"message": {"content": "Test response"}}]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_client.post.return_value = mock_response_obj
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await microservice_model.invoke({"messages": [{"role": "user", "content": "test"}]})

            mock_client.post.assert_called_once()
            # The result should be the mock response
            assert result == mock_response

    def test_with_config(self, microservice_model):
        """Test configuration support."""
        new_model = microservice_model.with_config({"test": "config"})

        assert isinstance(new_model, GuardrailsMicroserviceModel)
        assert new_model.base_url == microservice_model.base_url
        assert new_model.auth_token == microservice_model.auth_token

    def test_bind_tools(self, microservice_model):
        """Test tool binding support."""
        result = microservice_model.bind_tools(["tool1", "tool2"])

        assert result == microservice_model


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
    async def test_fetch_guardrails_models_success(self, component):
        """Test successful model fetching."""
        # Create mock models with id attributes (matching the actual API response)
        mock_model1 = Mock()
        mock_model1.id = "meta/llama-3.1-70b-instruct"
        # Ensure name attribute doesn't exist
        del mock_model1.name
        mock_model2 = Mock()
        mock_model2.id = "gpt-4o"
        # Ensure name attribute doesn't exist
        del mock_model2.name

        # Create mock response with data attribute
        mock_response = Mock()
        mock_response.data = [mock_model1, mock_model2]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.guardrail.models.list.return_value = mock_response
            mock_get_client.return_value = mock_client

            models = await component.fetch_guardrails_models()

            assert models == ["meta/llama-3.1-70b-instruct", "gpt-4o"]

    @pytest.mark.asyncio
    async def test_fetch_guardrails_models_error(self, component):
        """Test model fetching with error."""
        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.guardrail.models.list.side_effect = Exception("Client Error")
            mock_get_client.return_value = mock_client

            models = await component.fetch_guardrails_models()

            assert models == []

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
    async def test_build_model_success(self, component):
        """Test successful model building."""
        model = component.build_model()

        assert isinstance(model, GuardrailsMicroserviceModel)
        assert model.base_url == component.base_url
        assert model.auth_token == component.auth_token
        assert model.config_id == component.config
        assert model.model_name == component.model

    def test_build_model_missing_config(self):
        """Test model building with missing config."""
        component = NVIDIANeMoGuardrailsComponent(
            base_url="https://test.api.nvidia.com/nemo",
            auth_token="test_token",  # noqa: S106
            namespace="test_namespace",
            model="test_model",
        )

        with pytest.raises(ValueError, match="Guardrails configuration is required"):
            component.build_model()

    def test_build_model_missing_model(self):
        """Test model building with missing model."""
        component = NVIDIANeMoGuardrailsComponent(
            base_url="https://test.api.nvidia.com/nemo",
            auth_token="test_token",  # noqa: S106
            namespace="test_namespace",
            config="test_config",
            model="test_model",
        )

        with pytest.raises(ValueError, match="Model selection is required"):
            component.build_model()

    def test_build_model_missing_base_url(self):
        """Test model building with missing base URL."""
        component = NVIDIANeMoGuardrailsComponent()
        component.auth_token = "test_token"  # noqa: S105
        component.namespace = "test_namespace"
        component.config = "test_config"
        component.model = "test_model"
        # Clear the default base_url
        component.base_url = ""

        with pytest.raises(ValueError, match="Base URL is required"):
            component.build_model()

    def test_build_model_missing_auth_token(self):
        """Test model building with missing auth token."""
        component = NVIDIANeMoGuardrailsComponent(
            base_url="https://test.api.nvidia.com/nemo",
            namespace="test_namespace",
            config="test_config",
            model="test_model",
        )

        with pytest.raises(ValueError, match="Authentication token is required"):
            component.build_model()

    def test_build_model_missing_namespace(self):
        """Test model building with missing namespace."""
        component = NVIDIANeMoGuardrailsComponent(
            base_url="https://test.api.nvidia.com/nemo",
            auth_token="test_token",  # noqa: S106
            config="test_config",
            model="test_model",
        )
        # Clear the default namespace
        component.namespace = ""

        with pytest.raises(ValueError, match="Namespace is required"):
            component.build_model()

    @pytest.mark.asyncio
    async def test_update_build_config_guardrails_config(self, component):
        """Test build config update for guardrails config field."""
        build_config = {
            "config": {"options": [], "options_metadata": []},
            "model": {"options": [], "value": ""},
        }

        with patch.object(component, "fetch_guardrails_configs", new_callable=AsyncMock) as mock_fetch_configs:
            mock_fetch_configs.return_value = (["config1", "config2"], [{"icon": "Shield"}, {"icon": "Shield"}])

            await component.update_build_config(build_config, "config1", "config")

            assert build_config["config"]["options"] == ["config1", "config2"]
            # Model should not be affected by config refresh since they are independent
            assert build_config["model"]["options"] == []
            assert build_config["model"]["value"] == ""

    @pytest.mark.asyncio
    async def test_update_build_config_model_refresh(self, component):
        """Test build config update for model refresh."""
        build_config = {"model": {"options": [], "value": ""}}

        with patch.object(component, "fetch_guardrails_models", new_callable=AsyncMock) as mock_fetch_models:
            mock_fetch_models.return_value = ["model1", "model2"]

            await component.update_build_config(build_config, None, "model")

            assert build_config["model"]["options"] == ["model1", "model2"]
            assert build_config["model"]["value"] == "model1"

    @pytest.mark.asyncio
    async def test_update_build_config_model_refresh_no_config(self, component):
        """Test model refresh when no config is selected."""
        component.config = ""
        build_config = {"model": {"options": ["old_model"], "value": "old_model"}}

        # Mock the fetch_guardrails_models to return empty list
        with patch.object(component, "fetch_guardrails_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            await component.update_build_config(build_config, None, "model")

            assert build_config["model"]["options"] == []
            assert build_config["model"]["value"] == ""

    @pytest.mark.asyncio
    async def test_update_build_config_model_refresh_error(self, component):
        """Test model refresh with error."""
        build_config = {"model": {"options": ["old_model"], "value": "old_model"}}

        with patch.object(component, "fetch_guardrails_models", new_callable=AsyncMock) as mock_fetch_models:
            mock_fetch_models.side_effect = Exception("API Error")

            await component.update_build_config(build_config, None, "model")

            assert build_config["model"]["options"] == []
            assert build_config["model"]["value"] == ""

    @pytest.mark.asyncio
    async def test_text_response_success(self, component):
        """Test successful text response."""
        component.input_value = "Test input"
        component.system_message = "Test system message"

        mock_model = Mock()
        mock_model.invoke = AsyncMock(return_value={"choices": [{"message": {"content": "Test response"}}]})
        mock_model.with_config = Mock(return_value=mock_model)

        with (
            patch.object(component, "build_model", return_value=mock_model),
            patch.object(component, "get_langchain_callbacks", return_value=[]),
            patch.object(component, "get_project_name", return_value="test_project"),
        ):
            result = await component.text_response()

            assert result.text == "Test response"
            assert component.status == "Test response"

    @pytest.mark.asyncio
    async def test_text_response_empty_input(self, component):
        """Test text response with empty input."""
        component.input_value = ""
        component.system_message = ""

        with pytest.raises(ValueError, match="The message you want to send to the model is empty"):
            await component.text_response()

    @pytest.mark.asyncio
    async def test_text_response_streaming(self, component):
        """Test text response with streaming."""
        component.input_value = "Test input"
        component.stream = True

        mock_model = Mock()
        mock_model.invoke = AsyncMock(return_value={"choices": [{"message": {"content": "Test response"}}]})
        mock_model.with_config = Mock(return_value=mock_model)

        with (
            patch.object(component, "build_model", return_value=mock_model),
            patch.object(component, "get_langchain_callbacks", return_value=[]),
            patch.object(component, "get_project_name", return_value="test_project"),
            patch.object(component, "is_connected_to_chat_output", return_value=True),
            patch.object(component, "send_message", new_callable=AsyncMock) as mock_send,
        ):
            mock_message = Mock()
            mock_message.text = "Test response"
            mock_send.return_value = mock_message

            result = await component.text_response()

            assert result.text == "Test response"

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

    def test_mode_selection(self, component):
        """Test mode selection functionality."""
        # Test default mode
        assert getattr(component, "mode", "chat") == "chat"

        # Test mode attribute can be set
        component.mode = "check"
        assert component.mode == "check"

        # Test validation mode attribute
        component.validation_mode = "output"
        assert component.validation_mode == "output"

    @pytest.mark.asyncio
    async def test_build_model_check_mode(self, component):
        """Test build_model raises error in check mode."""
        component.mode = "check"

        with pytest.raises(NotImplementedError, match="Check mode does not provide a language model"):
            component.build_model()

    @pytest.mark.asyncio
    async def test_text_response_check_mode(self, component):
        """Test text_response in check mode."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"

        with patch.object(component, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "validated_output": Message(text="Validated input", error=False, category="message")
            }

            result = await component.text_response()

            assert result.text == "Validated input"
            assert result.error is False
            assert result.category == "message"
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_response_check_mode_error(self, component):
        """Test text_response in check mode with validation error."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Blocked input"

        with patch.object(component, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "validated_output": Message(text="I cannot process that input.", error=True, category="error")
            }

            result = await component.text_response()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_validated_output_method(self, component):
        """Test the validated_output method returns correct Message structure."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"

        with patch.object(component, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "validated_output": Message(text="Test input", error=False, category="message")
            }

            result = await component.validated_output()

            assert result.text == "Test input"
            assert result.error is False
            assert result.category == "message"
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_validated_output_method_error(self, component):
        """Test the validated_output method with validation error."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Blocked input"

        with patch.object(component, "process", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "validated_output": Message(text="I cannot process that input.", error=True, category="error")
            }

            result = await component.validated_output()

            assert result.text == "I cannot process that input."
            assert result.error is True
            assert result.category == "error"
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_response_chat_mode(self, component):
        """Test text_response in chat mode."""
        component.mode = "chat"

        with (
            patch.object(component, "build_model", return_value=Mock()),
            patch.object(component, "get_langchain_callbacks", return_value=[]),
            patch.object(component, "get_project_name", return_value="test_project"),
            patch.object(component, "_get_chat_result", new_callable=AsyncMock) as mock_chat_result,
        ):
            mock_chat_result.return_value = Message(text="Chat response")
            result = await component.text_response()

            assert result.text == "Chat response"
            mock_chat_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_validation_success_input_mode(self, component):
        """Test process method with successful input validation."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.blocked = False
        mock_response.choices = []  # Empty choices list for successful validation
        mock_response.choices = []  # Empty choices list for successful validation

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "Test input"
            assert validated_output.error is False
            assert validated_output.category == "message"
            assert component.status == "Input validated successfully"

            # Verify the guardrail.check was called with correct parameters
            mock_client.guardrail.check.assert_called_once_with(
                messages=[{"role": "user", "content": "Test input"}],
                guardrails={"config_id": "test_config"},
                extra_headers=component.get_auth_headers(),
            )

    @pytest.mark.asyncio
    async def test_process_validation_success_output_mode(self, component):
        """Test process method with successful output validation."""
        component.mode = "check"
        component.validation_mode = "output"
        component.input_value = "Test output"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.blocked = False
        mock_response.choices = []  # Empty choices list for successful validation

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "Test output"
            assert validated_output.error is False
            assert validated_output.category == "message"
            assert component.status == "Output validated successfully"

            # Verify the guardrail.check was called with correct parameters
            mock_client.guardrail.check.assert_called_once_with(
                messages=[{"role": "assistant", "content": "Test output"}],
                guardrails={"config_id": "test_config"},
                extra_headers=component.get_auth_headers(),
            )

    @pytest.mark.asyncio
    async def test_process_validation_blocked_input_mode(self, component):
        """Test process method with blocked input validation."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Blocked input"
        component.config = "test_config"

        # Mock the guardrail.check response for blocked validation
        mock_response = Mock()
        mock_response.blocked = True

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "I cannot process that input."
            assert validated_output.error is True
            assert validated_output.category == "error"
            assert component.status == "Input blocked by guardrails"

    @pytest.mark.asyncio
    async def test_process_validation_blocked_output_mode(self, component):
        """Test process method with blocked output validation."""
        component.mode = "check"
        component.validation_mode = "output"
        component.input_value = "Blocked output"
        component.config = "test_config"

        # Mock the guardrail.check response for blocked validation
        mock_response = Mock()
        mock_response.blocked = True

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "I cannot process that output."
            assert validated_output.error is True
            assert validated_output.category == "error"
            assert component.status == "Output blocked by guardrails"

    @pytest.mark.asyncio
    async def test_process_validation_fallback_choices_format(self, component):
        """Test process method with fallback choices format when blocked field not available."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response with choices format (fallback)
        mock_choice = Mock()
        mock_choice.finish_reason = "guardrail_blocked"
        mock_response = Mock()
        mock_response.blocked = None  # Simulate missing blocked field
        mock_response.choices = [mock_choice]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "I cannot process that input."
            assert validated_output.error is True
            assert validated_output.category == "error"
            assert component.status == "Input blocked by guardrails"

    @pytest.mark.asyncio
    async def test_process_validation_success_fallback_choices_format(self, component):
        """Test process method with successful validation using fallback choices format."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        # Mock the guardrail.check response with choices format (fallback) - no blocking
        mock_choice = Mock()
        mock_choice.finish_reason = "stop"  # Normal completion, not blocked
        mock_response = Mock()
        mock_response.blocked = None  # Simulate missing blocked field
        mock_response.choices = [mock_choice]

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "Test input"
            assert validated_output.error is False
            assert validated_output.category == "message"
            assert component.status == "Input validated successfully"

    @pytest.mark.asyncio
    async def test_process_validation_empty_input(self, component):
        """Test process method with empty input."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = ""
        component.system_message = ""

        with pytest.raises(ValueError, match="The message you want to validate is empty"):
            await component.process()

    @pytest.mark.asyncio
    async def test_process_validation_with_system_message(self, component):
        """Test process method with system message included."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.system_message = "System instruction"
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.blocked = False
        mock_response.choices = []  # Empty choices list for successful validation

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            # Should include system message in the validated text
            assert "System instruction" in validated_output.text
            assert "Test input" in validated_output.text

    @pytest.mark.asyncio
    async def test_process_validation_with_message_object(self, component):
        """Test process method with Message object input."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = Message(text="Test message")
        component.config = "test_config"

        # Mock the guardrail.check response for successful validation
        mock_response = Mock()
        mock_response.blocked = False
        mock_response.choices = []  # Empty choices list for successful validation

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await component.process()

            assert "validated_output" in result
            validated_output = result["validated_output"]
            assert validated_output.text == "Test message"
            assert validated_output.error is False

    @pytest.mark.asyncio
    async def test_process_validation_api_error(self, component):
        """Test process method with API error."""
        component.mode = "check"
        component.validation_mode = "input"
        component.input_value = "Test input"
        component.config = "test_config"

        with patch.object(component, "get_nemo_client") as mock_get_client:
            mock_client = Mock()
            mock_client.guardrail.check = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="API Error"):
                await component.process()

    @pytest.mark.asyncio
    async def test_process_validation_http_error_with_response(self, component):
        """Test process method with HTTP error that has response details."""
        component.mode = "check"
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
                await component.process()

    @pytest.mark.asyncio
    async def test_process_validation_nemo_exception_message(self, component):
        """Test process method with NeMo exception that has a message."""
        component.mode = "check"
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
                await component.process()
