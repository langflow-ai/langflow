from langchain_community.utilities.wolfram_alpha import WolframAlphaAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MultilineInput, SecretStrInput
from langflow.schema import Data


class WolframAlphaAPIComponent(LCToolComponent):
    display_name = "WolframAlphaAPI"
    description = "Call Wolfram Alpha API."
    name = "WolframAlphaAPI"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        SecretStrInput(name="app_id", display_name="App ID", required=True),
    ]

    def run_model(self) -> list[Data]:
        wrapper = self._build_wrapper()
        result_str = wrapper.run(self.input_value)
        data = [Data(text=result_str)]
        self.status = data
        return data

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return Tool(name="wolfram_alpha_api", description="Answers mathematical questions.", func=wrapper.run)

    def _build_wrapper(self) -> WolframAlphaAPIWrapper:
        return WolframAlphaAPIWrapper(wolfram_alpha_appid=self.app_id)  # type: ignore
