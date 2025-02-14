import pytest

from langflow.components.nvidia import NvidiaRerankComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNvidiaRerankComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NvidiaRerankComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "search_query": "What is AI?",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "nv-rerank-qa-mistral-4b:1",
            "api_key": "test_api_key",
            "search_results": [],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_update_build_config_with_valid_base_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "https://new.api.nvidia.com/v1", "base_url")
        assert "model" in updated_config
        assert "options" in updated_config["model"]
        assert updated_config["model"]["value"] == updated_config["model"]["options"][0]

    def test_update_build_config_with_invalid_base_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        with pytest.raises(ValueError):
            component.update_build_config(build_config, "", "base_url")

    async def test_rerank_documents(self, component_class, default_kwargs):
        default_kwargs["search_results"] = [Data(text="Document 1"), Data(text="Document 2")]
        component = component_class(**default_kwargs)
        result = await component.rerank_documents()
        assert result is not None
        assert isinstance(result, list)

    def test_build_vector_store_not_supported(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(NotImplementedError):
            component.build_vector_store()
