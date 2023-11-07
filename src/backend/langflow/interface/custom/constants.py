from langchain.prompts import PromptTemplate
from langchain.chains.base import Chain
from langchain.document_loaders.base import BaseLoader
from langchain.schema.embeddings import Embeddings
from langchain.llms.base import BaseLLM
from langchain.schema import BaseRetriever, Document
from langchain.text_splitter import TextSplitter
from langchain.tools import Tool
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseOutputParser
from langchain.schema.memory import BaseMemory
from langchain.memory.chat_memory import BaseChatMemory
from langchain.agents.agent import AgentExecutor

LANGCHAIN_BASE_TYPES = {
    "Chain": Chain,
    "AgentExecutor": AgentExecutor,
    "Tool": Tool,
    "BaseLLM": BaseLLM,
    "PromptTemplate": PromptTemplate,
    "BaseLoader": BaseLoader,
    "Document": Document,
    "TextSplitter": TextSplitter,
    "VectorStore": VectorStore,
    "Embeddings": Embeddings,
    "BaseRetriever": BaseRetriever,
    "BaseOutputParser": BaseOutputParser,
    "BaseMemory": BaseMemory,
    "BaseChatMemory": BaseChatMemory,
}

# Langchain base types plus Python base types
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **LANGCHAIN_BASE_TYPES,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}


DEFAULT_CUSTOM_COMPONENT_CODE = """from langflow import CustomComponent

from langchain.llms.base import BaseLLM
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import Document

import requests

class YourComponent(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return { "url": { "multiline": True, "required": True } }

    def build(self, url: str, llm: BaseLLM, prompt: PromptTemplate) -> Document:
        response = requests.get(url)
        chain = LLMChain(llm=llm, prompt=prompt)
        result = chain.run(response.text[:300])
        return Document(page_content=str(result))
"""
