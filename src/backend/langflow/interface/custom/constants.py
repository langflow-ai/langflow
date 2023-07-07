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


DEFAULT_CUSTOM_COMPONENT_CODE = """
from langflow import Prompt
from langchain.llms.base import BaseLLM
from langchain.chains import LLMChain
from langflow.interface.custom import CustomComponent
from langchain import PromptTemplate
from langchain.schema import Document
import requests

class YourComponent:
    display_name: str = "Your Component"
    description: str = "Your description"
    field_config = { "url": { "multiline": True, "required": True } }

    def build(self, url: str, llm: BaseLLM, template: Prompt) -> Document:
        response = requests.get(url)
        prompt = PromptTemplate.from_template(template)
        chain = LLMChain(llm=llm, prompt=prompt)
        result = chain.run(response.text[:300])
        return Document(page_content=str(result))
"""


# Create a new class that can be used as a type
# that returns type "prompt" if we get a certain param
