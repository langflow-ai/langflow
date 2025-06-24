from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import BoolInput, IntInput, MessageTextInput, MultilineInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


class WikipediaComponent(Component):
    display_name = "Wikipedia"
    description = "Call Wikipedia API."
    icon = "Wikipedia"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        MessageTextInput(name="lang", display_name="Language", value="en"),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
        BoolInput(name="load_all_available_meta", display_name="Load all available meta", value=False, advanced=True),
        IntInput(
            name="doc_content_chars_max", display_name="Document content characters max", value=4000, advanced=True
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="fetch_content_dataframe"),
    ]

    def run_model(self) -> DataFrame:
        return self.fetch_content_dataframe()

    def _build_wrapper(self) -> WikipediaAPIWrapper:
        return WikipediaAPIWrapper(
            top_k_results=self.k,
            lang=self.lang,
            load_all_available_meta=self.load_all_available_meta,
            doc_content_chars_max=self.doc_content_chars_max,
        )

    def fetch_content(self) -> list[Data]:
        wrapper = self._build_wrapper()
        docs = wrapper.load(self.input_value)
        data = [Data.from_document(doc) for doc in docs]
        self.status = data
        return data

    def fetch_content_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return DataFrame(data)
