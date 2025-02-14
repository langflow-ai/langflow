import pytest

from langflow.components.tools import WikidataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWikidataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WikidataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"query": "Python programming"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "wikidata", "file_name": "Wikidata"},
        ]

    def test_fetch_content_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.fetch_content()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, Data) for item in result)

    def test_fetch_content_no_results(self, component_class):
        component = component_class(query="nonexistentquery")
        result = component.fetch_content()
        assert len(result) == 1
        assert result[0].data["error"] == "No search results found for the given query."

    def test_fetch_content_http_error(self, mocker, component_class, default_kwargs):
        mocker.patch("httpx.get", side_effect=httpx.HTTPError("Mocked HTTP Error"))
        component = component_class(**default_kwargs)
        with pytest.raises(ToolException, match="HTTP Error in Wikidata Search API: Mocked HTTP Error"):
            component.fetch_content()

    def test_fetch_content_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.fetch_content_text()
        assert isinstance(result, Message)
        assert len(result.text) > 0
