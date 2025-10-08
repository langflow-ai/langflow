from langchain_community.utilities.wolfram_alpha import WolframAlphaAPIWrapper

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import MultilineInput, SecretStrInput
from lfx.io import Output
from lfx.schema.data import JSON, Data
from lfx.schema.dataframe import DataFrame, Table


class WolframAlphaAPIComponent(LCToolComponent):
    display_name = "WolframAlpha API"
    description = """Enables queries to WolframAlpha for computational data, facts, and calculations across various \
topics, delivering structured responses."""
    name = "WolframAlphaAPI"

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    inputs = [
        MultilineInput(
            name="input_value", display_name="Input Query", info="Example query: 'What is the population of France?'"
        ),
        SecretStrInput(name="app_id", display_name="WolframAlpha App ID", required=True),
    ]

    icon = "WolframAlphaAPI"

    def run_model(self) -> Table:
        return self.fetch_content_dataframe()

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return Tool(name="wolfram_alpha_api", description="Answers mathematical questions.", func=wrapper.run)

    def _build_wrapper(self) -> WolframAlphaAPIWrapper:
        return WolframAlphaAPIWrapper(wolfram_alpha_appid=self.app_id)

    def fetch_content(self) -> list[JSON]:
        wrapper = self._build_wrapper()
        result_str = wrapper.run(self.input_value)
        data = [Data(text=result_str)]
        self.status = data
        return data

    def fetch_content_dataframe(self) -> Table:
        """Convert the WolframAlpha results to a DataFrame.

        Returns: Table: A DataFrame containing the query results.
        """
        data = self.fetch_content()
        return DataFrame(data)
