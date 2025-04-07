import pytest
from langflow.components.models import GoogleGenerativeAIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleGenerativeAIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleGenerativeAIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_output_tokens": 100,
            "model_name": "gemini-1.5-pro",
            "api_key": "test_api_key",
            "top_p": 0.9,
            "temperature": 0.5,
            "n": 1,
            "top_k": 50,
            "tool_model_enabled": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "google_generative_ai", "file_name": "GoogleGenerativeAI"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None, "Model should not be None after building."
        assert hasattr(model, "generate"), "Model should have a 'generate' method."

    async def test_get_models(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = component.get_models()
        assert isinstance(models, list), "get_models should return a list."
        assert len(models) > 0, "Model list should not be empty."

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "gemini-1.5-pro", "model_name")
        assert "model_name" in updated_config, "Build config should contain 'model_name'."
        assert updated_config["model_name"]["value"] == "gemini-1.5-pro", "Model name should be updated correctly."
