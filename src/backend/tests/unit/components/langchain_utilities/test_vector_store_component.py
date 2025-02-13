import pytest
from langflow.components.langchain_utilities import VectoStoreRetrieverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectoStoreRetrieverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectoStoreRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"vectorstore": Mock()}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_config(self, component_class):
        component = component_class()
        config = component.build_config()
        assert "vectorstore" in config
        assert config["vectorstore"]["display_name"] == "Vector Store"
        assert config["vectorstore"]["type"] == VectorStore

    def test_build_retriever(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        retriever = component.build(default_kwargs["vectorstore"])
        assert isinstance(retriever, VectorStoreRetriever)
