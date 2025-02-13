import pytest

from langflow.components.models import GroqModel
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGroqModel(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GroqModel

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "base_url": "https://api.groq.com",
            "max_tokens": 100,
            "temperature": 0.5,
            "n": 1,
            "model_name": "gpt-3",
            "tool_model_enabled": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "groq", "file_name": "GroqModel"},
        ]

    async def test_get_models(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "https://api.groq.com", "base_url")
        assert "model_name" in updated_config
        assert "options" in updated_config["model_name"]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert hasattr(model, "generate")  # Assuming the model has a generate method
