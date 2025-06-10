from abc import abstractmethod

from langflow.custom.custom_component.component import Component
from langflow.field_typing import BaseDocumentCompressor
from langflow.io import DataInput, IntInput, MultilineInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.template.field.base import Output


class LCCompressorComponent(Component):
    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        DataInput(
            name="search_results",
            display_name="Search Results",
            info="Search Results from a Vector Store.",
            is_list=True,
        ),
        IntInput(name="top_n", display_name="Top N", value=3, advanced=True),
    ]

    outputs = [
        Output(
            display_name="Data",
            name="compressed_documents",
            method="Compressed Documents",
        ),
        Output(
            display_name="DataFrame",
            name="compressed_documents_as_dataframe",
            method="Compressed Documents as DataFrame",
        ),
    ]

    @abstractmethod
    def build_compressor(self) -> BaseDocumentCompressor:
        """Builds the Base Document Compressor object."""
        msg = "build_compressor method must be implemented."
        raise NotImplementedError(msg)

    async def compress_documents(self) -> list[Data]:
        """Compresses the documents retrieved from the vector store."""
        compressor = self.build_compressor()
        documents = compressor.compress_documents(
            query=self.search_query,
            documents=[passage.to_lc_document() for passage in self.search_results if isinstance(passage, Data)],
        )
        data = self.to_data(documents)
        self.status = data
        return data

    async def compress_documents_as_dataframe(self) -> DataFrame:
        """Compresses the documents retrieved from the vector store and returns a pandas DataFrame."""
        data_objs = await self.compress_documents()
        return DataFrame(data=data_objs)
