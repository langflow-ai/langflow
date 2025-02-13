import pytest

from langflow.components.embeddings import OllamaEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOllamaEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OllamaEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"model_name": "example_model", "base_url": "http://localhost:11434", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "ollama_embeddings", "file_name": "OllamaEmbeddings"},
        ]

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_embeddings()
        assert result is not None, "Embeddings should not be None."
        assert isinstance(result, list), "Embeddings should be a list."

    async def test_update_build_config_with_valid_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"base_url": {"value": "http://localhost:11434"}, "model_name": {"options": []}}
        updated_config = await component.update_build_config(build_config, "http://localhost:11434", "base_url")
        assert "options" in updated_config["model_name"], "Model options should be updated."

    async def test_update_build_config_with_invalid_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"base_url": {"value": "http://invalid-url"}, "model_name": {"options": []}}
        updated_config = await component.update_build_config(build_config, "http://invalid-url", "base_url")
        assert updated_config["model_name"]["options"] == [], "Model options should be empty for invalid URL."

    async def test_get_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = await component.get_model("http://localhost:11434")
        assert isinstance(models, list), "Model names should be returned as a list."
        assert all(isinstance(model, str) for model in models), "All model names should be strings."
