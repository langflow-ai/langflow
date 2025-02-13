import pytest
from langflow.components.langchain_utilities import VectorStoreInfoComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectorStoreInfoComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectorStoreInfoComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "vectorstore_name": "TestStore",
            "vectorstore_description": "A test vector store.",
            "input_vectorstore": Mock(),  # Mocking the VectorStore input
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vectorstore_info", "file_name": "VectorStoreInfo"},
        ]

    def test_build_info(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build_info()

        assert result is not None
        assert result.name == default_kwargs["vectorstore_name"]
        assert result.description == default_kwargs["vectorstore_description"]
        assert result.vectorstore == default_kwargs["input_vectorstore"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
