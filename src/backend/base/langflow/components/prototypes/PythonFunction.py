from typing import List

from langflow.custom import Component
from langflow.custom.utils import get_function
from langflow.io import CodeInput, Output
from langflow.schema import Data, dotdict
from langflow.schema.message import Message


class PythonFunctionComponent(Component):
    display_name = "Python Function"
    description = (
        "Define and execute a Python function that returns a Data object or a Message."
    )
    icon = "Python"
    name = "PythonFunction"
    beta = True

    inputs = [
        CodeInput(
            name="function_code",
            display_name="Function Code",
            info="The code for the function.",
        ),
    ]

    outputs = [
        Output(
            name="function_output",
            display_name="Function Output (Data)",
            method="execute_function_data",
        ),
        Output(
            name="function_output_str",
            display_name="Function Output (Message)",
            method="execute_function_message",
        ),
    ]

    async def execute_function(self) -> List[dotdict] | dotdict | str | List[str]:
        function_code = self.function_code

        if not function_code:
            return "No function code provided."

        try:
            func = get_function(function_code)
            return func()
        except Exception as e:
            return f"Error executing function: {str(e)}"

    async def execute_function_data(self) -> List[Data]:
        results = await self.execute_function()
        results = results if isinstance(results, list) else [results]
        data = [(Data(text=x) if isinstance(x, str) else Data(**x)) for x in results]
        return data

    async def execute_function_message(self) -> Message:
        results = await self.execute_function()
        results = results if isinstance(results, list) else [results]
        results = [str(x) for x in results]
        results = "\n".join(results)
        data = Message(text=results)
        return data
