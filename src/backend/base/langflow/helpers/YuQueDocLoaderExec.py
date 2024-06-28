import logging
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader

from langflow.helpers.YuQueTool import get_doc_detail_by_code, get_knowledge_detail

logger = logging.getLogger(__name__)


class YuQueDocLoaderExec(BaseLoader):

    def __init__(
            self,
            token: str = None,
            url: str = None,
            doc_type: str = None,
    ):
        self.token = token
        self.url = url
        self.doc_type = doc_type

    def load(self) -> Document:
        if self.doc_type == "Document":
            docs = get_doc_detail_by_code(self.token, self.url)
        else:
            docs = get_knowledge_detail(self.token, self.url)
        return Document(page_content=docs)
