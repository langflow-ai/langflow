import pytest
from langflow.components.tools import ExaSearchToolkit

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestExaSearchToolkit(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ExaSearchToolkit

    @pytest.fixture
    def default_kwargs(self):
        return {
            "metaphor_api_key": "test_api_key",
            "use_autoprompt": True,
            "search_num_results": 5,
            "similar_num_results": 5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_toolkit(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        assert toolkit is not None
        assert len(toolkit) == 3  # Should return three tools: search, get_contents, find_similar

    def test_tool_properties(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()

        search_tool = toolkit[0]
        assert search_tool.__name__ == "search"
        assert search_tool.__doc__ == "Call search engine with a query."

        get_contents_tool = toolkit[1]
        assert get_contents_tool.__name__ == "get_contents"
        assert get_contents_tool.__doc__ == "Get contents of a webpage."

        find_similar_tool = toolkit[2]
        assert find_similar_tool.__name__ == "find_similar"
        assert find_similar_tool.__doc__ == "Get search results similar to a given URL."
