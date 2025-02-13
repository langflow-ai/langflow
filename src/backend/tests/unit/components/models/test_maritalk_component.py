import pytest

from langflow.components.models import MaritalkModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMaritalkModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MaritalkModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_tokens": 512,
            "model_name": "sabia-2-small",
            "api_key": "test_api_key",
            "temperature": 0.1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "maritalk", "file_name": "MaritalkModelComponent"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.max_tokens == default_kwargs["max_tokens"]
        assert model.model == default_kwargs["model_name"]
        assert model.api_key == default_kwargs["api_key"]
        assert model.temperature == default_kwargs["temperature"]

    async def test_component_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None
