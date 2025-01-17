from collections.abc import Iterable
from typing import Any, Union

from langchain_community.graph_vectorstores.extractors import LinkExtractorTransformer
from langchain_community.graph_vectorstores.extractors.link_extractor import LinkExtractor
from langchain_community.graph_vectorstores.links import Link
from langchain_core.documents import BaseDocumentTransformer, Document
from loguru import logger

from langflow.base.document_transformers.model import LCDocumentTransformerComponent
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import DataInput, DictInput, StrInput
from langflow.services.cache.utils import CacheMiss

KeybertInput = Union[str, Document]


class KeybertLinkExtractorComponent(LCDocumentTransformerComponent, ComponentWithCache):
    display_name = "Keybert Link Extractor"
    description = "Extract keywords from text using KeyBERT."
    documentation = "https://python.langchain.com/api_reference/community/graph_vectorstores/langchain_community.graph_vectorstores.extractors.keybert_link_extractor.KeybertLinkExtractor.html"
    name = "KeybertLinkExtractor"

    inputs = [
        StrInput(name="kind", display_name="Kind of edge", value="kw", required=False),
        StrInput(
            name="model_name",
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

    def load_model(self) -> Any:
        try:
            import keybert

            self.embedding_model = self._shared_component_cache.get("kw_model")
            if isinstance(self.embedding_model, CacheMiss):
                logger.debug(f"Loading Keybert model {self.model_name}")
                self.embedding_model = keybert.KeyBERT(model=self.model_name)
                self._shared_component_cache.set("kw_model", self.embedding_model)
            return self.embedding_model

        except ImportError:
            raise ImportError(
                "keybert is required for KeybertLinkExtractor. Please install it with `pip install keybert`."
            ) from None

    def get_data_input(self) -> Any:
        return self.data_input

    def build_document_transformer(self) -> BaseDocumentTransformer:
        # Inject the KeyBERT model into the LinkExtractorTransformer.
        # This is the key difference between the langchain implementation and this workaround
        self.load_model()
        return LinkExtractorTransformer(
            [
                KeybertLinkExtractor(
                    kind=self.kind,
                    model=self.embedding_model,
                    extract_keywords_kwargs=self.extract_keywords_kwargs,
                )
            ]
        )


class KeybertLinkExtractor(LinkExtractor[KeybertInput]):
    def __init__(
        self,
        *,
        kind: str = "kw",
        model,
        extract_keywords_kwargs: dict[str, Any] | None = None,
    ):
        self._kw_model = model
        self._kind = kind
        self._extract_keywords_kwargs = extract_keywords_kwargs or {}

    def extract_one(self, input: KeybertInput) -> set[Link]:  # noqa: A002
        keywords = self._kw_model.extract_keywords(
            input if isinstance(input, str) else input.page_content,
            **self._extract_keywords_kwargs,
        )
        return {Link.bidir(kind=self._kind, tag=kw[0]) for kw in keywords}

    def extract_many(
        self,
        inputs: Iterable[KeybertInput],
    ) -> Iterable[set[Link]]:
        inputs = list(inputs)
        if len(inputs) == 1:
            # Even though we pass a list, if it contains one item, keybert will
            # flatten it. This means it's easier to just call the special case
            # for one item.
            yield self.extract_one(inputs[0])
        elif len(inputs) > 1:
            strs = [i if isinstance(i, str) else i.page_content for i in inputs]
            extracted = self._kw_model.extract_keywords(strs, **self._extract_keywords_kwargs)
            for keywords in extracted:
                yield {Link.bidir(kind=self._kind, tag=kw[0]) for kw in keywords}
