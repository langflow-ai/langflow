from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import ToolException
from langflow.components.search.yahoo import YahooFinanceMethod, YfinanceComponent
from langflow.custom.utils import build_custom_component_template
from langflow.schema import Data


class TestYfinanceComponent:
    @pytest.fixture
    def component_class(self):
        return YfinanceComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"symbol": "AAPL", "method": YahooFinanceMethod.GET_INFO, "num_news": 5, "_session_id": "test-session"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "Yahoo Finance"
        assert component.icon == "trending-up"
        assert "yfinance" in component.description

    def test_template_structure(self, component_class):
        component = component_class()
        frontend_node, _ = build_custom_component_template(component)

        assert "template" in frontend_node
        input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

        expected_inputs = ["symbol", "method", "num_news"]
        for input_name in expected_inputs:
            assert input_name in input_names

    @patch("langflow.components.search.yahoo.yf.Ticker")
    def test_fetch_info(self, mock_ticker, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        # Setup mock
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        mock_instance.info = {"companyName": "Apple Inc."}

        result = component.fetch_content()

        assert isinstance(result, list)
        assert len(result) == 1
        assert "Apple Inc." in result[0].text

    @patch("langflow.components.search.yahoo.yf.Ticker")
    def test_fetch_news(self, mock_ticker, component_class):
        component = component_class(symbol="AAPL", method=YahooFinanceMethod.GET_NEWS, num_news=2)

        # Setup mock
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        mock_instance.news = [
            {"title": "News 1", "link": "http://example.com/1"},
            {"title": "News 2", "link": "http://example.com/2"},
        ]

        result = component.fetch_content()

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert "News 1" in result[0].text
        assert "http://example.com/1" in result[0].text

    def test_error_handling(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        with patch.object(component, "_fetch_yfinance_data") as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            with pytest.raises(ToolException):
                component.fetch_content()
