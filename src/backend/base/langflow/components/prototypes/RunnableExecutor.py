from langflow.custom import Component
from langflow.inputs import HandleInput, MessageTextInput
from langflow.schema.message import Message
from langflow.template import Output


class RunnableExecComponent(Component):
    description = "Execute a runnable. It will try to guess the input and output keys."
    display_name = "Runnable Executor"
    name = "RunnableExecutor"
    beta: bool = True

    inputs = [
        MessageTextInput(name="input_value", display_name="Input", required=True),
        HandleInput(
            name="runnable",
            display_name="Agent Executor",
            input_types=["Chain", "AgentExecutor", "Agent", "Runnable"],
            required=True,
        ),
        MessageTextInput(
            name="input_key",
            display_name="Input Key",
            value="input",
            advanced=True,
        ),
        MessageTextInput(
            name="output_key",
            display_name="Output Key",
            value="output",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Text",
            name="text",
            method="build_executor",
        ),
    ]

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

    def build_executor(self) -> Message:
        input_dict, status = self.get_input_dict(self.runnable, self.input_key, self.input_value)
        result = self.runnable.invoke(input_dict)
        result_value, _status = self.get_output(result, self.input_key, self.output_key)
        status += _status
        status += f"\n\nOutput: {result_value}\n\nRaw Output: {result}"
        self.status = status
        return result_value
