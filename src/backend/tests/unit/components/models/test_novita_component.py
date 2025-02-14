import pytest
from langflow.components.models import NovitaModelComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNovitaModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NovitaModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "model_name": "gpt-3.5-turbo",
            "max_tokens": 100,
            "temperature": 0.5,
            "json_mode": False,
            "seed": 42,
            "model_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "novita", "file_name": "NovitaModel"},
        ]

    def test_get_models_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_models_failure(self, mocker, component_class, default_kwargs):
        mocker.patch("requests.get", side_effect=Exception("Network Error"))
        component = component_class(**default_kwargs)
        models = component.get_models()
        assert "Error fetching models: Network Error" in component.status
        assert models == ["gpt-3.5-turbo"]  # Assuming this is the default

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = await component.build_model()
        assert model is not None
        assert hasattr(model, "model_name")
        assert model.model_name == default_kwargs["model_name"]

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"model_name": {"options": []}}
        updated_config = component.update_build_config(build_config, "test_api_key", "api_key")
        assert "options" in updated_config["model_name"]
        assert len(updated_config["model_name"]["options"]) > 0
