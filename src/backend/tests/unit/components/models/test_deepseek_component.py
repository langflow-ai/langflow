import pytest

from langflow.components.models import DeepSeekModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDeepSeekModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DeepSeekModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "max_tokens": 100,
            "model_kwargs": {},
            "json_mode": False,
            "model_name": "deepseek-chat",
            "api_base": "https://api.deepseek.com",
            "temperature": 1.0,
            "seed": 1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "deepseek", "file_name": "DeepSeekModelComponent"},
        ]

    def test_get_models_without_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = None
        models = component.get_models()
        assert models == ["deepseek-chat"]

    def test_get_models_with_api_key(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mock_response = {"data": [{"id": "model1"}, {"id": "model2"}]}
        mocker.patch("requests.get", return_value=mocker.Mock(status_code=200, json=lambda: mock_response))
        component.api_key = "test_api_key"
        models = component.get_models()
        assert models == ["model1", "model2"]

    def test_get_models_with_request_exception(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch("requests.get", side_effect=Exception("Request failed"))
        component.api_key = "test_api_key"
        models = component.get_models()
        assert models == ["deepseek-chat"]
        assert component.status == "Error fetching models: Request failed"

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"model_name": {"options": []}}
        updated_config = component.update_build_config(build_config, "test_value", "model_name")
        assert "model_name" in updated_config
        assert len(updated_config["model_name"]["options"]) > 0
