export const custom = `from langflow import CustomComponent

from langchain.llms.base import BaseLLM
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document
from langflow.field_typing import NestedDict

import requests

class YourComponent(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return { "file": { "file_type": ["json"], } }

    def build(self, url: str,file:str,integer:int,nested:NestedDict,flt:float,boolean:bool,lisst:list[str],dictionary:dict, llm: BaseLLM, prompt: PromptTemplate) -> Document:

        return "test"`;
