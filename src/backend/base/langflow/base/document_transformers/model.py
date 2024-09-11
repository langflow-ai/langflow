from abc import abstractmethod
from typing import Any

from langchain_core.documents import BaseDocumentTransformer

from langflow.custom import Component
from langflow.io import Output
from langflow.schema import Data
from langflow.utils.util import build_loader_repr_from_data


class LCDocumentTransformerComponent(Component):
    trace_type = "document_transformer"
    outputs = [
        Output(display_name="Data", name="data", method="transform_data"),
    ]

    def transform_data(self) -> list[Data]:
        data_input = self.get_data_input()
        documents = []

        if not isinstance(data_input, list):
            data_input = [data_input]

        for _input in data_input:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        transformer = self.build_document_transformer()
        docs = transformer.transform_documents(documents)
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
    def build_document_transformer(self) -> BaseDocumentTransformer:
        """
        Build the text splitter.
        """
        pass
