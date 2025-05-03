import pytest
from langflow.components.tools import YfinanceComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYfinanceComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YfinanceComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "symbol": "AAPL",
            "method": "get_news",
            "num_news": 5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "yfinance", "file_name": "YfinanceComponent"},
        ]

    async def test_fetch_content(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.fetch_content()
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result)

    async def test_fetch_content_text(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.fetch_content_text()
        assert isinstance(result, Message)
        assert isinstance(result.text, str)

    async def test_invalid_symbol(self, component_class):
        component = component_class(symbol="INVALID", method="get_info")
        with pytest.raises(ToolException):
            await component.fetch_content()

    async def test_all_versions_have_a_file_name_defined(self, file_names_mapping):
        if not file_names_mapping:
            pytest.skip("No file names mapping defined for this component.")
        for mapping in file_names_mapping:
            assert mapping["file_name"] is not None, "file_name must be defined for all versions."
