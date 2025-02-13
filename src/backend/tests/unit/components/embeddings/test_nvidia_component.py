import pytest

from langflow.components.embeddings import NVIDIAEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNVIDIAEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NVIDIAEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": "nvidia/nv-embed-v1",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "nvidia_api_key": "NVIDIA_API_KEY",
            "temperature": 0.1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "NVIDIAEmbeddings"},
        ]

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "https://new.api.nvidia.com/v1", "base_url")

        assert "model" in updated_config
        assert "options" in updated_config["model"]
        assert updated_config["model"]["value"] == updated_config["model"]["options"][0]

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        embeddings = await component.build_embeddings()

        assert embeddings is not None
        assert hasattr(embeddings, "model")
