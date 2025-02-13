import pytest
from langflow.components.deactivated.embed import EmbedComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestEmbedComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return EmbedComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "texts": ["Hello world", "Langflow is great"],
            "embbedings": Mock(),  # Mocking the Embeddings object
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_method(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build(**default_kwargs)
        assert result is not None
        assert hasattr(result, "vector")
        assert len(result.vector) == len(default_kwargs["texts"])

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None
