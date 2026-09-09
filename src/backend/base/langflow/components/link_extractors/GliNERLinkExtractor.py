from typing import Any

from langchain_community.graph_vectorstores.extractors import LinkExtractorTransformer, GLiNERLinkExtractor
from langchain_core.documents import BaseDocumentTransformer

from langflow.base.document_transformers.model import LCDocumentTransformerComponent
from langflow.inputs import DataInput, StrInput, DictInput


class GLiNERLinkExtractorComponent(LCDocumentTransformerComponent):
    display_name = "GliNER Link Extractor"
    description = "Extract named entities links from documents using GLiNER"
    documentation = "https://python.langchain.com/api_reference/community/graph_vectorstores/langchain_community.graph_vectorstores.extractors.gliner_link_extractor.GLiNERLinkExtractor.html"
    name = "GLiNERLinkExtractor"

    inputs = [
        StrInput(name="labels", display_name="List of kinds of entities to extract", required=True, is_list=True),
        StrInput(name="kind", display_name="Kind of edge", value="entity"),
        StrInput(name="model", display_name="GLiNER model to use", value="urchade/gliner_mediumv2.1"),
        DictInput(
            name="extract_kwargs",
            display_name="Arguments to pass to GLiNER.",
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
            [GLiNERLinkExtractor(self.labels, kind=self.kind, model=self.model, extract_kwargs=self.extract_kwargs)]
        )
