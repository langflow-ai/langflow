
from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, Chain
from typing import Union, Callable

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

        # Implement the logic to create and return the appropriate chain based on the chain_type
        # This could be a placeholder for now, as the specific chain loading function is not defined.
        # Replace with actual implementation when available.
        return load_qa_chain(llm=llm, chain_type=chain_type)

# Assuming there is a function or class `load_qa_chain` that creates the chain
# based on the `chain_type` and `llm`. This is a placeholder for the actual
# implementation which should be replaced with the correct function/class call.
def load_qa_chain(llm: BaseLanguageModel, chain_type: str) -> Union[Chain, Callable]:
    # Implement the logic to create and return the appropriate chain based on the chain_type
    pass
