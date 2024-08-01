from abc import abstractmethod
from typing import Any

from langchain_text_splitters import TextSplitter

from langflow.custom import Component
from langflow.io import Output
from langflow.schema import Data
from langflow.utils.util import build_loader_repr_from_data


class LCTextSplitterComponent(Component):
    trace_type = "text_splitter"
    outputs = [
        Output(display_name="Data", name="data", method="split_data"),
    ]

    def _validate_outputs(self):
        required_output_methods = ["text_splitter"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def split_data(self) -> list[Data]:
        data_input = self.get_data_input()
        documents = []

        if not isinstance(data_input, list):
            data_input = [data_input]

        for _input in data_input:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        splitter = self.build_text_splitter()
        docs = splitter.split_documents(documents)
        data = self.to_data(docs)
        self.repr_value = build_loader_repr_from_data(data)
        return data

    @abstractmethod
    def get_data_input(self) -> Any:
        """
        Get the data input.
        """
        pass

    @abstractmethod
    def build_text_splitter(self) -> TextSplitter:
        """
        Build the text splitter.
        """
        pass
