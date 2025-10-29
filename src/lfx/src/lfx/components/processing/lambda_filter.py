from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, HandleInput, IntInput, MultilineInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from collections.abc import Callable


class LambdaFilterComponent(Component):
    display_name = "Smart Transform"
    description = "Uses an LLM to generate a function for filtering or transforming structured data."
    documentation: str = "https://docs.langflow.org/components-processing#smart-transform"
    icon = "square-function"
    name = "Smart Transform"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The structured data to filter or transform using a lambda function.",
            input_types=["Data", "DataFrame"],
            is_list=True,
            required=True,
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            info="Connect the 'Language Model' output from your LLM component here.",
            input_types=["LanguageModel"],
            required=True,
        ),
        MultilineInput(
            name="filter_instruction",
            display_name="Instructions",
            info=(
                "Natural language instructions for how to filter or transform the data using a lambda function. "
                "Example: Filter the data to only include items where the 'status' is 'active'."
            ),
            value="Filter the data to...",
            required=True,
        ),
        IntInput(
            name="sample_size",
            display_name="Sample Size",
            info="For large datasets, number of items to sample from head/tail.",
            value=1000,
            advanced=True,
        ),
        IntInput(
            name="max_size",
            display_name="Max Size",
            info="Number of characters for the data to be considered large.",
            value=30000,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Output",
            name="data_output",
            method="process_as_data",
        ),
        Output(
            display_name="Output",
            name="dataframe_output",
            method="process_as_dataframe",
        ),
    ]

    def get_data_structure(self, data):
        """Extract the structure of data, replacing values with their types."""
        if isinstance(data, list):
            # For lists, get structure of first item if available
            if data:
                return [self.get_data_structure(data[0])]
            return []
        if isinstance(data, dict):
            return {k: self.get_data_structure(v) for k, v in data.items()}
        # For primitive types, return the type name
        return type(data).__name__

    def _validate_lambda(self, lambda_text: str) -> bool:
        """Validate the provided lambda function text."""
        # Return False if the lambda function does not start with 'lambda' or does not contain a colon
        return lambda_text.strip().startswith("lambda") and ":" in lambda_text

    async def _execute_lambda(self) -> Any:
        self.log(str(self.data))

        # Convert input to a unified format
        if isinstance(self.data, list):
            # Handle list of Data or DataFrame objects
            combined_data = []
            for item in self.data:
                if isinstance(item, DataFrame):
                    # DataFrame to list of dicts
                    combined_data.extend(item.to_dict(orient="records"))
                elif hasattr(item, "data"):
                    # Data object
                    if isinstance(item.data, dict):
                        combined_data.append(item.data)
                    elif isinstance(item.data, list):
                        combined_data.extend(item.data)

            # If we have a single dict, unwrap it so lambdas can access it directly
            if len(combined_data) == 1 and isinstance(combined_data[0], dict):
                data = combined_data[0]
            elif len(combined_data) == 0:
                data = {}
            else:
                data = combined_data  # type: ignore[assignment]
        elif isinstance(self.data, DataFrame):
            # Single DataFrame to list of dicts
            data = self.data.to_dict(orient="records")
        elif hasattr(self.data, "data"):
            # Single Data object
            data = self.data.data
        else:
            data = self.data

        dump = json.dumps(data)
        self.log(str(data))

        llm = self.llm
        instruction = self.filter_instruction
        sample_size = self.sample_size

        # Get data structure and samples
        data_structure = self.get_data_structure(data)
        dump_structure = json.dumps(data_structure)
        self.log(dump_structure)

        # For large datasets, sample from head and tail
        if len(dump) > self.max_size:
            data_sample = (
                f"Data is too long to display... \n\n First lines (head): {dump[:sample_size]} \n\n"
                f" Last lines (tail): {dump[-sample_size:]})"
            )
        else:
            data_sample = dump

        self.log(data_sample)

        prompt = f"""Given this data structure and examples, create a Python lambda function that
                    implements the following instruction:

                    Data Structure:
                    {dump_structure}

                    Example Items:
                    {data_sample}

                    Instruction: {instruction}

                    Return ONLY the lambda function and nothing else. No need for ```python or whatever.
                    Just a string starting with lambda.
                    """

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        self.log(response_text)

        # Extract lambda using regex
        lambda_match = re.search(r"lambda\s+\w+\s*:.*?(?=\n|$)", response_text)
        if not lambda_match:
            msg = f"Could not find lambda in response: {response_text}"
            raise ValueError(msg)

        lambda_text = lambda_match.group().strip()
        self.log(lambda_text)

        # Validation is commented out as requested
        if not self._validate_lambda(lambda_text):
            msg = f"Invalid lambda format: {lambda_text}"
            raise ValueError(msg)

        # Create and apply the function
        fn: Callable[[Any], Any] = eval(lambda_text)  # noqa: S307

        # Apply the lambda function to the data
        return fn(data)

    async def process_as_data(self) -> Data:
        """Process the data and return as a Data object."""
        result = await self._execute_lambda()

        # Convert result to Data based on type
        if isinstance(result, dict):
            return Data(data=result)
        if isinstance(result, list):
            return Data(data={"_results": result})
        # For other types, convert to string
        return Data(data={"text": str(result)})

    async def process_as_dataframe(self) -> DataFrame:
        """Process the data and return as a DataFrame."""
        result = await self._execute_lambda()

        # Convert result to DataFrame based on type
        if isinstance(result, list):
            # Check if it's a list of dicts
            if all(isinstance(item, dict) for item in result):
                return DataFrame(result)
            # List of non-dicts: wrap each value
            return DataFrame([{"value": item} for item in result])
        if isinstance(result, dict):
            # Single dict becomes single-row DataFrame
            return DataFrame([result])
        # Other types: convert to string and wrap
        return DataFrame([{"value": str(result)}])
