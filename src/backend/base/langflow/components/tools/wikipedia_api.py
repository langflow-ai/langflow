from typing import cast

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import BoolInput, IntInput, MessageTextInput, MultilineInput
from langflow.schema import Data


class WikipediaAPIComponent(LCToolComponent):
    display_name = "Wikipedia API [Deprecated]"
    description = "Call Wikipedia API."
    name = "WikipediaAPI"
    icon = "Wikipedia"
    legacy = True

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        MessageTextInput(name="lang", display_name="Language", value="en"),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
        BoolInput(name="load_all_available_meta", display_name="Load all available meta", value=False, advanced=True),
        IntInput(
            name="doc_content_chars_max", display_name="Document content characters max", value=4000, advanced=True
        ),
    ]

    def run_model(self) -> list[Data]:
        wrapper = self._build_wrapper()
        docs = wrapper.load(self.input_value)
        data = [Data.from_document(doc) for doc in docs]
        self.status = data
        return data

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return cast("Tool", WikipediaQueryRun(api_wrapper=wrapper))

    def _build_wrapper(self) -> WikipediaAPIWrapper:
        return WikipediaAPIWrapper(
            top_k_results=self.k,
            lang=self.lang,
            load_all_available_meta=self.load_all_available_meta,
            doc_content_chars_max=self.doc_content_chars_max,
        )
