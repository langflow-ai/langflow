import pytest

from langflow.components.models import HuggingFaceEndpointsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHuggingFaceEndpointsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HuggingFaceEndpointsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_id": "meta-llama/Llama-3.3-70B-Instruct",
            "custom_model": "",
            "max_new_tokens": 512,
            "top_k": None,
            "top_p": 0.95,
            "typical_p": 0.95,
            "temperature": 0.8,
            "repetition_penalty": None,
            "inference_endpoint": "https://api-inference.huggingface.co/models/",
            "task": "text-generation",
            "huggingfacehub_api_token": "test_token",
            "model_kwargs": {},
            "retry_attempts": 1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "huggingface", "file_name": "HuggingFaceEndpoints"},
        ]

    def test_get_api_url_with_custom_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.model_id = "custom"
        component.custom_model = "my_custom_model"
        expected_url = f"{component.inference_endpoint}{component.custom_model}"
        assert component.get_api_url() == expected_url

    def test_get_api_url_with_default_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        expected_url = f"{component.inference_endpoint}{component.model_id}"
        assert component.get_api_url() == expected_url

    def test_update_build_config_show_custom_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"custom_model": {"show": False, "required": False}}
        updated_config = component.update_build_config(build_config, "custom", "model_id")
        assert updated_config["custom_model"]["show"] is True
        assert updated_config["custom_model"]["required"] is True

    def test_update_build_config_hide_custom_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"custom_model": {"show": True, "required": True}}
        updated_config = component.update_build_config(build_config, "meta-llama/Llama-3.3-70B-Instruct", "model_id")
        assert updated_config["custom_model"]["show"] is False
        assert updated_config["custom_model"]["value"] == ""

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_model()
        assert result is not None
