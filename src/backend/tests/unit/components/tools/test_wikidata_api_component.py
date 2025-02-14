import pytest
from langflow.components.tools import WikidataAPIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWikidataAPIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WikidataAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"query": "Python programming"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "wikidata", "file_name": "WikidataAPI"},
        ]

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "wikidata_search_api"
        assert tool.description == "Perform similarity search on Wikidata API"

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        results = await component.run_model()
        assert isinstance(results, list)
        assert all(isinstance(data, dict) for data in results)
        assert all("label" in data for data in results)

    async def test_run_model_no_results(self, component_class):
        component = component_class(query="nonexistentquery")
        with pytest.raises(ToolException, match="No search results found for the given query."):
            await component.run_model()
