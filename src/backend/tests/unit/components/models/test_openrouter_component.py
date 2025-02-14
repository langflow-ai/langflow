import pytest

from langflow.components.models import OpenRouterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenRouterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "site_url": "https://example.com",
            "app_name": "TestApp",
            "provider": "Loading providers...",
            "model_name": "Select a provider first",
            "temperature": 0.7,
            "max_tokens": 100,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "open_router", "file_name": "OpenRouter"},
        ]

    def test_fetch_models_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = component.fetch_models()
        assert isinstance(models, dict)
        assert "Error" not in models

    def test_fetch_models_failure(self, component_class, default_kwargs, mocker):
        mocker.patch("httpx.Client.get", side_effect=httpx.HTTPError("Test error"))
        component = component_class(**default_kwargs)
        models = component.fetch_models()
        assert "Error" in models
        assert models["Error"][0]["name"] == "Error fetching models: Test error"

    def test_build_model_without_selection(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Please select a model"):
            component.build_model()

    def test_build_model_without_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.model_name = "SomeModel"
        component.api_key = ""
        with pytest.raises(ValueError, match="API key is required"):
            component.build_model()

    def test_build_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.model_name = "SomeModel"
        component.api_key = "test_api_key"
        model = component.build_model()
        assert model is not None

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "provider": {"options": [], "value": ""},
            "model_name": {"options": [], "value": ""},
        }
        updated_config = component.update_build_config(build_config, "SomeProvider", "provider")
        assert "SomeProvider" in updated_config["provider"]["options"]
        assert updated_config["model_name"]["value"] == "Select a provider first"
