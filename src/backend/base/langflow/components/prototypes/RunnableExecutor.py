from langchain_core.runnables import Runnable

from langflow.custom import CustomComponent
from langflow.field_typing import Text


class RunnableExecComponent(CustomComponent):
    description = "Execute a runnable. It will try to guess the input and output keys."
    display_name = "Runnable Executor"
    beta: bool = True
    field_order = [
        "input_key",
        "output_key",
        "input_value",
        "runnable",
    ]

    def build_config(self):
        return {
            "input_key": {
                "display_name": "Input Key",
                "info": "The key to use for the input.",
                "advanced": True,
            },
            "input_value": {
                "display_name": "Inputs",
                "info": "The inputs to pass to the runnable.",
            },
            "runnable": {
                "display_name": "Runnable",
                "info": "The runnable to execute.",
                "input_types": ["Chain", "AgentExecutor", "Agent", "Runnable"],
            },
            "output_key": {
                "display_name": "Output Key",
                "info": "The key to use for the output.",
                "advanced": True,
            },
        }

    def get_output(self, result, input_key, output_key):
        """
        Retrieves the output value from the given result dictionary based on the specified input and output keys.

        Args:
            result (dict): The result dictionary containing the output value.
            input_key (str): The key used to retrieve the input value from the result dictionary.
            output_key (str): The key used to retrieve the output value from the result dictionary.

        Returns:
            tuple: A tuple containing the output value and the status message.

        """
        possible_output_keys = ["answer", "response", "output", "result", "text"]
        status = ""
        result_value = None

        if output_key in result:
            result_value = result.get(output_key)
        elif len(result) == 2 and input_key in result:
            # get the other key from the result dict
            other_key = [k for k in result if k != input_key][0]
            if other_key == output_key:
                result_value = result.get(output_key)
            else:
                status += f"Warning: The output key is not '{output_key}'. The output key is '{other_key}'."
                result_value = result.get(other_key)
        elif len(result) == 1:
            result_value = list(result.values())[0]
        elif any(k in result for k in possible_output_keys):
            for key in possible_output_keys:
                if key in result:
                    result_value = result.get(key)
                    status += f"Output key: '{key}'."
                    break
            if result_value is None:
                result_value = result
                status += f"Warning: The output key is not '{output_key}'."
        else:
            result_value = result
            status += f"Warning: The output key is not '{output_key}'."

        return result_value, status

    def get_input_dict(self, runnable, input_key, input_value):
        """
        Returns a dictionary containing the input key-value pair for the given runnable.

        Args:
            runnable: The runnable object.
            input_key: The key for the input value.
            input_value: The value for the input key.

        Returns:
            input_dict: A dictionary containing the input key-value pair.
            status: A status message indicating if the input key is not in the runnable's input keys.
        """
        input_dict = {}
        status = ""
        if hasattr(runnable, "input_keys"):
            # Check if input_key is in the runnable's input_keys
            if input_key in runnable.input_keys:
                input_dict[input_key] = input_value
            else:
                input_dict = {k: input_value for k in runnable.input_keys}
                status = f"Warning: The input key is not '{input_key}'. The input key is '{runnable.input_keys}'."
        return input_dict, status

    def build(
        self,
        input_value: Text,
        runnable: Runnable,
        input_key: str = "input",
        output_key: str = "output",
    ) -> Text:
        input_dict, status = self.get_input_dict(runnable, input_key, input_value)
        result = runnable.invoke(input_dict)
        result_value, _status = self.get_output(result, input_key, output_key)
        status += _status
        status += f"\n\nOutput: {result_value}\n\nRaw Output: {result}"
        self.status = status
        return result_value
