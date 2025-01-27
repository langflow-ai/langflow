from typing import Any

from langflow.field_typing import BaseDocumentCompressor
from langflow.base.compressors.model import LCCompressorComponent
from langflow.io import DropdownInput
from langflow.template.field.base import Output


class VoyageAIRerankComponent(LCCompressorComponent):
    display_name = "Voyage AI Rerank"
    description = "Rerank documents using the Voyage AI API."
    name = "VoyageAIRerank"

    inputs = [
        *LCCompressorComponent.inputs,
        DropdownInput(
            name="model",
            display_name="Model",
            options=["rerank-2-lite", "rerank-2"],
            value="rerank-2-lite",
        ),
    ]

    outputs = [
        Output(
            display_name="Reranked Documents",
            name="reranked_documents",
            method="rerank_documents",
        ),
    ]

    def build_compressor(self) -> BaseDocumentCompressor:
        try:
            from langchain_voyageai import VoyageAIRerank
        except ImportError as e:
            msg = "Please install langchain-voyageai to use the Voyage AI model."
            raise ImportError(msg) from e
        return VoyageAIRerank(
            voyageai_api_key=self.api_key,
            model=self.model,
            top_k=self.top_n
        )
