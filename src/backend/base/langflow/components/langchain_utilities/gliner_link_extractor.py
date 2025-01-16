from typing import Any
from typing import Any, Dict, Iterable, Optional, Set, Union, List

from langflow.base.document_transformers.model import LCDocumentTransformerComponent
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import DataInput, StrInput, DictInput
from langflow.services.cache.utils import CacheMiss

from langchain_core._api import beta
from langchain_core.documents import Document
from langchain_community.graph_vectorstores.extractors import LinkExtractorTransformer
from langchain_core.documents import BaseDocumentTransformer
from langchain_community.graph_vectorstores.extractors.link_extractor import LinkExtractor
from langchain_community.graph_vectorstores.links import Link

from loguru import logger

GLiNERInput = Union[str, Document]

class GLiNERLinkExtractorComponent(LCDocumentTransformerComponent, ComponentWithCache):
    display_name = "GliNER Link Extractor"
    description = "Extract named entities links from documents using GLiNER"
    documentation = "https://python.langchain.com/api_reference/community/graph_vectorstores/langchain_community.graph_vectorstores.extractors.gliner_link_extractor.GLiNERLinkExtractor.html"
    name = "GLiNERLinkExtractor"

    inputs = [
        # Note that I removed the isList from the labels input.
        StrInput(name="labels", display_name="Command separated list of kinds of entities to extract", required=True),
        StrInput(name="kind", display_name="Kind of edge", value="entity", required=True),
        StrInput(name="model_name", display_name="GLiNER model to use", value="urchade/gliner_mediumv2.1", required=True),
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

    def load_model (self) -> Any:
        try:
            from gliner import GLiNER

            self.embedding_model = self._shared_component_cache.get("gliner_model")
            if isinstance(self.embedding_model, CacheMiss):
                logger.debug(f"Loading GLiNER model {self.model_name}")
                self.embedding_model = GLiNER.from_pretrained(self.model_name)
                self._shared_component_cache.set("gliner_model", self.embedding_model)
            else:
                logger.debug(f"GLiNER already loaded {self.model_name}")
            return self.embedding_model
        
        except ImportError:
            raise ImportError(
                "gliner is required for GlinerLinkExtractor. "
                "Please install it with `pip install gliner`."
            ) from None

    def get_data_input(self) -> Any:
        return self.data_input

    def build_document_transformer(self) -> BaseDocumentTransformer:
        self.load_model()
        
        # This is a hack to cvonvert a list of a single string to a list of strings. Should be handled by the UI
        self.labels = self.labels[0].split(",") if isinstance(self.labels, list) else self.labels.split(",")
        
        return LinkExtractorTransformer(
            [GLiNERLinkExtractor(self.labels, kind=self.kind, model=self.embedding_model, extract_kwargs=self.extract_kwargs)]
        )
        
class GLiNERLinkExtractor(LinkExtractor[GLiNERInput]):
    def __init__(
        self,
        labels: List[str],
        *,
        kind: str = "entity",
        model,
        extract_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._glinermodel = model
        self._labels = labels
        self._kind = kind
        self._extract_kwargs = extract_kwargs or {}

    def extract_one(self, input: GLiNERInput) -> Set[Link]:  # noqa: A002
        return next(iter(self.extract_many([input])))

    def extract_many(
        self,
        inputs: Iterable[GLiNERInput],
    ) -> Iterable[Set[Link]]:
        strs = [i if isinstance(i, str) else i.page_content for i in inputs]
        for entities in self._glinermodel.batch_predict_entities(
            strs, self._labels, **self._extract_kwargs
        ):
            yield {
                Link.bidir(kind=f"{self._kind}:{e['label']}", tag=e["text"])
                for e in entities
            }


