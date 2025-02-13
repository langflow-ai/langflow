import pytest

from langflow.components.langchain_utilities import SpiderTool
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSpiderTool(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SpiderTool

    @pytest.fixture
    def default_kwargs(self):
        return {
            "spider_api_key": "test_api_key",
            "url": "https://example.com",
            "mode": "scrape",
            "limit": 5,
            "depth": 2,
            "blacklist": "/ignore",
            "whitelist": "/include",
            "readability": True,
            "request_timeout": 10,
            "metadata": True,
            "params": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "spider", "file_name": "SpiderTool"},
        ]

    async def test_crawl_with_params(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.params = {"data": {"limit": 10, "depth": 3}}
        result = await component.run()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(record, Data) for record in result)

    async def test_crawl_without_params(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(record, Data) for record in result)

    async def test_invalid_mode(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.mode = "invalid_mode"
        with pytest.raises(ValueError, match="Invalid mode: invalid_mode. Must be 'scrape' or 'crawl'."):
            await component.run()
