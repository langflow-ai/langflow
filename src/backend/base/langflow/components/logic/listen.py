from langflow.custom import Component
from langflow.io import Output, StrInput
from langflow.schema import Data


class ListenComponent(Component):
    display_name = "Listen"
    description = "A component to listen for a notification."
    name = "Listen"
    beta: bool = True
    icon = "Radio"
    inputs = [StrInput(name="context_key", display_name="Context Key", info="The key of the context to listen for.")]

    outputs = [Output(name="data", display_name="Data", method="build")]

    def build(self) -> Data:
        return self.ctx.get(self.context_key, Data(data={}))
