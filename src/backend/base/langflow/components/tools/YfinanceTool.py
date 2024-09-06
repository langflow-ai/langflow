from typing import cast

from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Data, Tool
from langflow.inputs.inputs import MessageTextInput
from langflow.template.field.base import Output


class YfinanceToolComponent(LCToolComponent):
    display_name = "Yahoo Finance News Tool"
    description = "Tool for interacting with Yahoo Finance News."
    name = "YFinanceTool"

    def build_tool(self) -> Tool:
        return cast(Tool, YahooFinanceNewsTool())

    def run_model(self) -> Data:
        tool = self.build_tool()
        return tool.run(self.input_value)
