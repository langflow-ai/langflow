from langchain_core.runnables import Runnable

from langflow.field_typing import Text
from langflow.interface.custom.custom_component import CustomComponent


class RunnableExecComponent(CustomComponent):
    documentation: str = "http://docs.langflow.org/components/custom"
    display_name = "Runnable Executor"
    beta: bool = True

    def build_config(self):
        return {
            "input_key": {
                "display_name": "Input Key",
                "info": "The key to use for the input.",
            },
            "input_value": {
                "display_name": "Inputs",
                "info": "The inputs to pass to the runnable.",
            },
            "runnable": {
                "display_name": "Runnable",
                "info": "The runnable to execute.",
            },
            "output_key": {
                "display_name": "Output Key",
                "info": "The key to use for the output.",
            },
        }

    def build(
        self,
        input_key: str,
        input_value: Text,
        runnable: Runnable,
        output_key: str = "output",
    ) -> Text:
        result = runnable.invoke({input_key: input_value})
        result = result.get(output_key)
        self.status = result
        return result
