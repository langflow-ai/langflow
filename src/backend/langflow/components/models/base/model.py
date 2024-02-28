from langchain_core.runnables import Runnable

from langflow import CustomComponent


class LCModelComponent(CustomComponent):
    display_name: str = "Model Name"
    description: str = "Model Description"

    def get_result(self, output: Runnable, stream: bool, input_value: str):
        """
        Retrieves the result from the output of a Runnable object.

        Args:
            output (Runnable): The output object to retrieve the result from.
            stream (bool): Indicates whether to use streaming or invocation mode.
            input_value (str): The input value to pass to the output object.

        Returns:
            The result obtained from the output object.
        """
        if stream:
            result = output.stream(input_value)
        else:
            message = output.invoke(input_value)
            result = message.content if hasattr(message, "content") else message
            self.status = result
        return result
