from abc import abstractmethod
from langflow.custom import Component
from langflow.field_typing import BaseDocumentCompressor
from langflow.io import MultilineInput, DataInput, SecretStrInput, IntInput
from langflow.template.field.base import Output
from langflow.schema import Data


class LCCompressorComponent(Component):

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
        ),
        DataInput(
            name="search_results",
            display_name="Search Results",
            info="Search Results from a Vector Store.",
            is_list=True,
        ),
        IntInput(
            name="top_n",
            display_name="Top N",
            value=3,
            advanced=True
        ),
    ]

    outputs = [
        Output(
            display_name="Compressed Documents",
            name="compressed_documents",
            method="Compressed Documents",
        ),
    ]

    @abstractmethod
    def build_compressor(self) -> BaseDocumentCompressor:
        """Builds the Base Document Compressor object."""
        msg = "build_vector_store method must be implemented."
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
