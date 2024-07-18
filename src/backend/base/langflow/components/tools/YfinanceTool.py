from typing import cast

from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output


class YfinanceToolComponent(Component):
    display_name = "Yahoo Finance News Tool"
    description = "Tool for interacting with Yahoo Finance News."
    name = "YFinanceTool"

    outputs = [
        Output(display_name="Tool", name="tool", method="build_tool"),
    ]

    def build_tool(self) -> Tool:
        return cast(Tool, YahooFinanceNewsTool())
