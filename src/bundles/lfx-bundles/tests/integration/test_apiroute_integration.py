from unittest.mock import patch

import httpx
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
        assert kwargs["openai_api_key"] == mock_api_key
        assert kwargs["openai_api_base"] == "https://global.api-route.com/v1"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 1000

    @patch("lfx_bundles.apiroute.apiroute.httpx.get")
    def test_fetch_models_sorts_valid_response(self, mock_get, component, mock_api_key):
        component.api_key = mock_api_key
        mock_get.return_value.json.return_value = {
            "data": [
                {"id": "z-model", "name": "Zed", "context_length": 1000},
                {"id": "a-model", "name": "Alpha"},
            ]
        }

        assert component.fetch_models() == [
            {"id": "a-model", "name": "Alpha", "context": 0},
            {"id": "z-model", "name": "Zed", "context": 1000},
        ]
        mock_get.assert_called_once_with(
            "https://global.api-route.com/v1/models",
            headers={"Authorization": f"Bearer {mock_api_key}"},
            timeout=10.0,
        )

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            [],
            {},
            {"data": None},
            {"data": {}},
            {"data": [None]},
            {"data": [{"id": 123}]},
            {"data": [{"id": "valid"}, {"name": "missing id"}]},
            {"data": [{"id": "valid", "name": 123}]},
        ],
    )
    @patch("lfx_bundles.apiroute.apiroute.httpx.get")
    def test_fetch_models_rejects_invalid_payload(self, mock_get, component, payload):
        mock_get.return_value.json.return_value = payload

        assert component.fetch_models() == []

    @patch("lfx_bundles.apiroute.apiroute.httpx.get")
    def test_update_build_config_uses_fallback_after_invalid_response(self, mock_get, component):
        mock_get.return_value.json.return_value = {"data": [None]}
        build_config = {"model_name": {"options": [], "value": ""}}

        updated = component.update_build_config(build_config, "", "model_name")

        assert updated["model_name"]["options"][0] == "claude-3-7-sonnet-20250219"
        assert updated["model_name"]["value"] == "claude-3-7-sonnet-20250219"

    def test_update_build_config_uses_live_models(self, component):
        build_config = {"model_name": {"options": [], "value": ""}}
        models = [{"id": "test-model", "name": "Test Model", "context": 0}]

        with patch.object(component, "fetch_models", return_value=models):
            updated = component.update_build_config(build_config, "", "model_name")

        assert updated["model_name"]["options"] == ["test-model"]
        assert updated["model_name"]["tooltips"] == {"test-model": "Test Model"}

    @pytest.mark.parametrize(
        ("api_key", "model_name", "error"),
        [
            ("", "test-model", "API key is required"),
            ("test-key", "", "Please select a model"),
            ("test-key", "Loading...", "Please select a model"),
        ],
    )
    def test_build_model_rejects_missing_configuration(self, component, api_key, model_name, error):
        component.api_key = api_key
        component.model_name = model_name

        with pytest.raises(ValueError, match=error):
            component.build_model()

    @patch("lfx_bundles.apiroute.apiroute.httpx.get")
    def test_fetch_models_handles_http_error(self, mock_get, component):
        request = httpx.Request("GET", "https://global.api-route.com/v1/models")
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad response", request=request, response=httpx.Response(500, request=request)
        )

        assert component.fetch_models() == []
