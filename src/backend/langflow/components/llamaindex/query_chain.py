"""Query Chain."""

from typing import Optional, List, cast, Callable, Union
from langflow import CustomComponent
from langflow.utils.util import build_loader_repr_from_documents
from llama_index.schema import Document, TextNode
from llama_index.node_parser import SentenceSplitter
from llama_index import VectorStoreIndex, ServiceContext
from langflow.field_typing import Object, BaseLanguageModel, Chain
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.llms import LangChainLLM
from langflow.field_typing import BasePromptTemplate


class QueryChainComponent(CustomComponent):
    display_name: str = "Query Chain" 
    description: str = "Synthesizes an answer from a query engine."
    
    def build_config(self):
        return {
            "query_engine": {
                "display_name": "Query Engine",
                "info": "The query engine to use",
            },
            "prompt": {
                "display_name": "Prompt",
                "info": "The prompt to use",
            },
        }
    
    def build(
        self,
        query_engine: Object,
        prompt: BasePromptTemplate,
    ) -> Union[Chain, Callable]:
        """Build."""
        def query_chain_fn(*args, **kwargs) -> str:
            fmt_prompt = prompt.format(**kwargs)
            return str(query_engine.query(fmt_prompt))

        return query_chain_fn
        
