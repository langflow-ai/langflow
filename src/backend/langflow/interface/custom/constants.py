from langchain import PromptTemplate
from langchain.chains.base import Chain
from langchain.document_loaders.base import BaseLoader
from langchain.embeddings.base import Embeddings
from langchain.llms.base import BaseLLM
from langchain.schema import BaseRetriever, Document
from langchain.text_splitter import TextSplitter
from langchain.tools import Tool
from langchain.vectorstores.base import VectorStore


LANGCHAIN_BASE_TYPES = {
    "Chain": Chain,
    "Tool": Tool,
    "BaseLLM": BaseLLM,
    "PromptTemplate": PromptTemplate,
    "BaseLoader": BaseLoader,
    "Document": Document,
    "TextSplitter": TextSplitter,
    "VectorStore": VectorStore,
    "Embeddings": Embeddings,
    "BaseRetriever": BaseRetriever,
}
