from typing import Any

from langchain_community.graph_vectorstores.extractors import LinkExtractorTransformer, KeybertLinkExtractor
from langchain_core.documents import BaseDocumentTransformer

from langflow.base.document_transformers.model import LCDocumentTransformerComponent
from langflow.inputs import DataInput, StrInput, DictInput


class KeybertLinkExtractorComponent(LCDocumentTransformerComponent):
    display_name = "Keybert Link Extractor"
    description = "Extract keywords from text using KeyBERT."
    documentation = "https://python.langchain.com/api_reference/community/graph_vectorstores/langchain_community.graph_vectorstores.extractors.keybert_link_extractor.KeybertLinkExtractor.html"
    name = "KeybertLinkExtractor"

    inputs = [
        StrInput(name="kind", display_name="Kind of edge", value="kw", required=False),
        StrInput(
            name="embedding_model",
            display_name="Embedding model to use with KeyBERT",
            value="all-MiniLM-L6-v2",
            required=False,
        ),
        DictInput(
            name="extract_keywords_kwargs",
            display_name="Arguments to pass to KeyBERT.",
            is_list=True,
            advanced=True,
        ),
        DataInput(
            name="data_input",
            display_name="Input",
            info="The texts from which to extract links.",
            input_types=["Document", "Data"],
        ),
    ]

    def get_data_input(self) -> Any:
        return self.data_input

    def build_document_transformer(self) -> BaseDocumentTransformer:
        return LinkExtractorTransformer(
            [
                KeybertLinkExtractor(
                    kind=self.kind,
                    embedding_model=self.embedding_model,
                    extract_keywords_kwargs=self.extract_keywords_kwargs,
                )
            ]
        )
