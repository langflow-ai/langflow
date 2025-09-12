from lfx.base.compressors.model import LCCompressorComponent
from lfx.field_typing import BaseDocumentCompressor
from lfx.inputs.inputs import SecretStrInput
from lfx.io import DropdownInput
from lfx.template.field.base import Output


class CohereRerankComponent(LCCompressorComponent):
    display_name = "Cohere Rerank"
    description = "Rerank documents using the Cohere API."
    name = "CohereRerank"
    icon = "Cohere"

    inputs = [
        *LCCompressorComponent.inputs,
        SecretStrInput(
            name="api_key",
            display_name="Cohere API Key",
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "rerank-english-v3.0",
                "rerank-multilingual-v3.0",
                "rerank-english-v2.0",
                "rerank-multilingual-v2.0",
            ],
            value="rerank-english-v3.0",
        ),
    ]

    outputs = [
        Output(
            display_name="Reranked Documents",
            name="reranked_documents",
            method="compress_documents",
        ),
    ]

    def build_compressor(self) -> BaseDocumentCompressor:  # type: ignore[type-var]
        try:
            from langchain_cohere import CohereRerank
        except ImportError as e:
            msg = "Please install langchain-cohere to use the Cohere model."
            raise ImportError(msg) from e
        return CohereRerank(
            cohere_api_key=self.api_key,
            model=self.model,
            top_n=self.top_n,
        )
