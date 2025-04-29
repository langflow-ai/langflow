import pytest
from langflow.components.langchain_utilities import RetrieverToolComponent
from langflow.field_typing import BaseRetriever
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRetrieverToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RetrieverToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "retriever": Mock(spec=BaseRetriever),
            "name": "Test Tool",
            "description": "A tool for testing purposes.",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build(**default_kwargs)
        assert tool is not None
        assert tool.name == "Test Tool"
        assert tool.description == "A tool for testing purposes."

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
