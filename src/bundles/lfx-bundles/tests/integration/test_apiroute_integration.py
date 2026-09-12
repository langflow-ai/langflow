from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_openai")

from lfx_bundles.apiroute.apiroute import APIRouteComponent


class TestAPIRouteIntegration:
    """Integration tests for APIRoute component."""

    @pytest.fixture
    def component(self):
        """Create an APIRoute component instance for testing."""
        return APIRouteComponent()

    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing."""
        return "test-apiroute-key"

    def test_component_import(self):
        """Test that the APIRoute component can be imported."""
        from lfx_bundles.apiroute.apiroute import APIRouteComponent

        assert APIRouteComponent is not None

    def test_component_instantiation(self, component):
        """Test that the component can be instantiated."""
        assert component is not None
        assert component.display_name == "API Route"
        assert component.icon == "APIRoute"

    def test_component_inputs_present(self, component):
        """Test that all expected inputs are present."""
        input_names = [input_.name for input_ in component.inputs]

        expected_inputs = [
            "api_key",
            "model_name",
            "temperature",
            "max_tokens",
        ]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    @patch("lfx_bundles.apiroute.apiroute.ChatOpenAI")
    def test_build_model(self, mock_chat_openai, component, mock_api_key):
        """Test building the model."""
        component.api_key = mock_api_key
        component.model_name = "claude-3-7-sonnet-20250219"
        component.temperature = 0.7
        component.max_tokens = 1000

        model = component.build_model()
        assert model is not None
        mock_chat_openai.assert_called_once()
        _, kwargs = mock_chat_openai.call_args
        assert kwargs["model"] == "claude-3-7-sonnet-20250219"
        assert kwargs["openai_api_base"] == "https://global.api-route.com/v1"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 1000
