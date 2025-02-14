import pytest

from langflow.components.tools import YfinanceToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYfinanceToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YfinanceToolComponent

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
            {"version": "1.0.0", "module": "yfinance", "file_name": "YfinanceTool"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(data, dict) for data in result), "Each result should be a dictionary."

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == "yahoo_finance"
        assert tool.description == "Access financial data and market information from Yahoo Finance."

    async def test_yahoo_finance_tool_error_handling(self, component_class):
        component = component_class(symbol="INVALID", method="get_info")
        with pytest.raises(ToolException):
            component.run_model()
