from langflow import CustomComponent

from langchain.llms.base import BaseLLM
from langchain.chains import LLMChain
from langchain import PromptTemplate
from langchain.schema import Document

import requests


class YourComponent(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return {"url": {"multiline": True, "required": True}}

    def build(self, url: str, llm: BaseLLM, prompt: PromptTemplate) -> Document:
        response = requests.get(url)
        chain = LLMChain(llm=llm, prompt=prompt)
        result = chain.run(response.text[:300])
        return Document(page_content=str(result))
