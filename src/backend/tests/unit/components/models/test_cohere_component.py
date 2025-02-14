import pytest
from langflow.components.models import CohereComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCohereComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CohereComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"cohere_api_key": "test_api_key", "temperature": 0.75, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "cohere", "file_name": "Cohere"},
            {"version": "1.1.0", "module": "cohere", "file_name": "cohere"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.temperature == default_kwargs["temperature"]
        assert model.cohere_api_key == default_kwargs["cohere_api_key"]

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None
