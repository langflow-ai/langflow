import pytest

from langflow.components.models import NVIDIAModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNVIDIAModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NVIDIAModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_tokens": 50,
            "model_name": "nvidia_model",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "tool_model_enabled": False,
            "api_key": "NVIDIA_API_KEY",
            "temperature": 0.5,
            "seed": 1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "models", "file_name": "NVIDIAModelComponent"},
        ]

    async def test_get_models_with_tool_model_enabled(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.tool_model_enabled = True
        models = component.get_models(tool_model_enabled=True)
        assert isinstance(models, list)
        assert all(isinstance(model, str) for model in models)

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "https://new.api.nvidia.com/v1", "base_url")
        assert "model_name" in updated_config
        assert updated_config["model_name"]["options"] is not None

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert hasattr(model, "generate")  # Assuming the model has a generate method
