import pytest

from langflow.components.models import OpenAIModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenAIModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenAIModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_tokens": 100,
            "model_kwargs": {},
            "json_mode": False,
            "model_name": "gpt-3.5-turbo",
            "openai_api_base": "https://api.openai.com/v1",
            "api_key": "test_api_key",
            "temperature": 0.7,
            "seed": 42,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "openai", "file_name": "OpenAIModel"},
            {"version": "1.1.0", "module": "openai", "file_name": "OpenAIModel"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.model == default_kwargs["model_name"]
        assert model.temperature == default_kwargs["temperature"]
        assert model.max_tokens == default_kwargs["max_tokens"]

    async def test_invalid_api_key(self, component_class, default_kwargs):
        default_kwargs["api_key"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="API key is required"):
            component.build_model()

    async def test_json_mode(self, component_class, default_kwargs):
        default_kwargs["json_mode"] = True
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model.response_format == {"type": "json_object"}
