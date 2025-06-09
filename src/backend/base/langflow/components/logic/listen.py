from langflow.custom import Component
from langflow.io import Output, StrInput
from langflow.schema.data import Data


class ListenComponent(Component):
    display_name = "Listen"
    description = "A component to listen for a notification."
    name = "Listen"
    beta: bool = True
    icon = "Radio"
    inputs = [
        StrInput(
            name="context_key",
            display_name="Context Key",
            info="The key of the context to listen for.",
            input_types=["Data", "Message", "DataFrame"],
        )
    ]

    outputs = [Output(name="data", display_name="Data", method="build", cache=False)]

    def build(self) -> Data:
        """Retrieves data from the component context using the specified context key.

        Returns:
            The Data object associated with the context key, or an empty Data object if the key is not found.
        """
        return self.ctx.get(self.context_key, Data(text=""))
