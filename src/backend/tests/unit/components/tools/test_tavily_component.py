import pytest
from langflow.components.tools import TavilySearchComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestTavilySearchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return TavilySearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "query": "What is AI?",
            "search_depth": "advanced",
            "topic": "general",
            "max_results": 5,
            "include_images": True,
            "include_answer": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tavily_search", "file_name": "TavilySearch"},
        ]

    async def test_fetch_content(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.fetch_content()
        assert isinstance(result, list)
        assert all(isinstance(data, Data) for data in result)

    async def test_fetch_content_text(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.fetch_content_text()
        assert isinstance(result, Message)
        assert result.text is not None

    async def test_invalid_api_key(self, component_class):
        invalid_kwargs = {
            "api_key": "invalid_api_key",
            "query": "What is AI?",
            "search_depth": "advanced",
            "topic": "general",
            "max_results": 5,
            "include_images": True,
            "include_answer": True,
        }
        component = await self.component_setup(component_class, invalid_kwargs)
        result = await component.fetch_content()
        assert len(result) == 1
        assert "error" in result[0].data
        assert "HTTP error occurred" in result[0].text

    async def test_request_error_handling(self, component_class):
        # Simulate a request error by using an invalid URL
        component = await self.component_setup(
            component_class,
            {
                "api_key": "test_api_key",
                "query": "What is AI?",
                "search_depth": "advanced",
                "topic": "general",
                "max_results": 5,
                "include_images": True,
                "include_answer": True,
            },
        )
        component.fetch_content = Mock(side_effect=httpx.RequestError("Request error"))
        result = await component.fetch_content()
        assert len(result) == 1
        assert "error" in result[0].data
        assert "Request error occurred" in result[0].text
