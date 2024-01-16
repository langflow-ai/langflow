
from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, Chain
from typing import Union, Callable
from langchain.chains.combine_documents.base import BaseCombineDocumentsChain

class CombineDocsChainComponent(CustomComponent):
    display_name = "CombineDocsChain"
    description = "Load question answering chain."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "chain_type": {
                "display_name": "Chain Type",
                "options": ['stuff', 'map_reduce', 'map_rerank', 'refine'],
            },
        }

    def build(
        self,
        llm: BaseLanguageModel,
        chain_type: str,
    ) -> Union[Chain, Callable]:
        if chain_type not in ['stuff', 'map_reduce', 'map_rerank', 'refine']:
            raise ValueError(f"Invalid chain_type: {chain_type}")

        return BaseCombineDocumentsChain()