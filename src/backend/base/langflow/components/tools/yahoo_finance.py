import ast
import pprint
from enum import Enum

import yfinance as yf
from langchain.tools import StructuredTool
from langchain_core.tools import ToolException
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DropdownInput, IntInput, MessageTextInput
from langflow.schema import Data


class YahooFinanceMethod(Enum):
    GET_INFO = "get_info"
    GET_NEWS = "get_news"
    GET_ACTIONS = "get_actions"
    GET_ANALYSIS = "get_analysis"
    GET_BALANCE_SHEET = "get_balance_sheet"
    GET_CALENDAR = "get_calendar"
    GET_CASHFLOW = "get_cashflow"
    GET_INSTITUTIONAL_HOLDERS = "get_institutional_holders"
    GET_RECOMMENDATIONS = "get_recommendations"
    GET_SUSTAINABILITY = "get_sustainability"
    GET_MAJOR_HOLDERS = "get_major_holders"
    GET_MUTUALFUND_HOLDERS = "get_mutualfund_holders"
    GET_INSIDER_PURCHASES = "get_insider_purchases"
    GET_INSIDER_TRANSACTIONS = "get_insider_transactions"
    GET_INSIDER_ROSTER_HOLDERS = "get_insider_roster_holders"
    GET_DIVIDENDS = "get_dividends"
    GET_CAPITAL_GAINS = "get_capital_gains"
    GET_SPLITS = "get_splits"
    GET_SHARES = "get_shares"
    GET_FAST_INFO = "get_fast_info"
    GET_SEC_FILINGS = "get_sec_filings"
    GET_RECOMMENDATIONS_SUMMARY = "get_recommendations_summary"
    GET_UPGRADES_DOWNGRADES = "get_upgrades_downgrades"
    GET_EARNINGS = "get_earnings"
    GET_INCOME_STMT = "get_income_stmt"


class YahooFinanceSchema(BaseModel):
    symbol: str = Field(..., description="The stock symbol to retrieve data for.")
    method: YahooFinanceMethod = Field(YahooFinanceMethod.GET_INFO, description="The type of data to retrieve.")
    num_news: int | None = Field(5, description="The number of news articles to retrieve.")


class YfinanceToolComponent(LCToolComponent):
    display_name = "Yahoo Finance [DEPRECATED]"
    description = """Uses [yfinance](https://pypi.org/project/yfinance/) (unofficial package) \
to access financial data and market information from Yahoo Finance."""
    icon = "trending-up"
    name = "YahooFinanceTool"
    legacy = True

    inputs = [
        MessageTextInput(
            name="symbol",
            display_name="Stock Symbol",
            info="The stock symbol to retrieve data for (e.g., AAPL, GOOG).",
        ),
        DropdownInput(
            name="method",
            display_name="Data Method",
            info="The type of data to retrieve.",
            options=list(YahooFinanceMethod),
            value="get_news",
        ),
        IntInput(
            name="num_news",
            display_name="Number of News",
            info="The number of news articles to retrieve (only applicable for get_news).",
            value=5,
        ),
    ]

    def run_model(self) -> list[Data]:
        return self._yahoo_finance_tool(
            self.symbol,
            self.method,
            self.num_news,
        )

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="yahoo_finance",
            description="Access financial data and market information from Yahoo Finance.",
            func=self._yahoo_finance_tool,
            args_schema=YahooFinanceSchema,
        )

    def _yahoo_finance_tool(
        self,
        symbol: str,
        method: YahooFinanceMethod,
        num_news: int | None = 5,
    ) -> list[Data]:
        ticker = yf.Ticker(symbol)

        try:
            if method == YahooFinanceMethod.GET_INFO:
                result = ticker.info
            elif method == YahooFinanceMethod.GET_NEWS:
                result = ticker.news[:num_news]
            else:
                result = getattr(ticker, method.value)()

            result = pprint.pformat(result)

            if method == YahooFinanceMethod.GET_NEWS:
                data_list = [Data(data=article) for article in ast.literal_eval(result)]
            else:
                data_list = [Data(data={"result": result})]

        except Exception as e:
            error_message = f"Error retrieving data: {e}"
            logger.debug(error_message)
            self.status = error_message
            raise ToolException(error_message) from e

        return data_list
