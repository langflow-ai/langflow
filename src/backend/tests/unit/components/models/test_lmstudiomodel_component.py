import pytest

from langflow.components.models import LMStudioModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLMStudioModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LMStudioModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "base_url": "http://localhost:1234/v1",
            "model_name": "gpt-3.5-turbo",
            "max_tokens": 100,
            "temperature": 0.7,
            "api_key": "LMSTUDIO_API_KEY",
            "seed": 42,
            "model_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "lm_studio", "file_name": "LMStudioModel"},
            {"version": "1.1.0", "module": "lm_studio", "file_name": "lm_studio_model"},
        ]

    async def test_update_build_config_with_valid_model_name(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"base_url": {"value": "http://localhost:1234/v1", "load_from_db": False}}
        updated_config = await component.update_build_config(build_config, "gpt-3.5-turbo", "model_name")

        assert "options" in updated_config["model_name"]
        assert isinstance(updated_config["model_name"]["options"], list)

    async def test_get_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = await component.get_model("http://localhost:1234/v1")

        assert isinstance(models, list)

    async def test_get_model_failure(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(
            ValueError, match="Could not retrieve models. Please, make sure the LM Studio server is running."
        ):
            await component.get_model("http://invalid-url")

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()

        assert model is not None
        assert model.model == default_kwargs["model_name"]
        assert model.temperature == default_kwargs["temperature"]
        assert model.max_tokens == default_kwargs["max_tokens"]

    async def test_exception_message_extraction(self, component_class):
        component = component_class()
        from openai import BadRequestError

        exception = BadRequestError("Bad request", body={"message": "Invalid input"})
        message = component._get_exception_message(exception)

        assert message == "Invalid input"
