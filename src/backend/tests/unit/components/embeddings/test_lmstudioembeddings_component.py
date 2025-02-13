import pytest

from langflow.components.embeddings import LMStudioEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLMStudioEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LMStudioEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": "default-model",
            "base_url": "http://localhost:1234/v1",
            "api_key": "LMSTUDIO_API_KEY",
            "temperature": 0.1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_update_build_config_with_load_from_db(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"base_url": {"load_from_db": True, "value": "http://localhost:1234/v1"}, "model": {}}
        updated_config = await component.update_build_config(build_config, "model", "model")
        assert "options" in updated_config["model"]

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

    async def test_build_embeddings_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()
        assert embeddings is not None

    async def test_build_embeddings_import_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(
            ImportError, match="Please install langchain-nvidia-ai-endpoints to use LM Studio Embeddings."
        ):
            component.build_embeddings()
