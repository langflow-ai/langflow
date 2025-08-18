from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from langflow.custom.custom_component.component import Component
from langflow.io import DataInput, HandleInput, IntInput, MultilineInput, Output
from langflow.schema.data import Data
from langflow.utils.data_structure import get_data_structure

if TYPE_CHECKING:
    from collections.abc import Callable


class LambdaFilterComponent(Component):
    display_name = "Smart Function"
    description = "Uses an LLM to generate a function for filtering or transforming structured data."
    documentation: str = "https://docs.langflow.org/components-processing#smart-function"
    icon = "square-function"
    name = "Smart Function"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The structured data to filter or transform using a lambda function.",
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
            display_name="Filtered Data",
            name="filtered_data",
            method="filter_data",
        ),
    ]

    def get_data_structure(self, data):
        """Extract the structure of a dictionary, replacing values with their types."""
        return {k: get_data_structure(v) for k, v in data.items()}

    def _validate_lambda(self, lambda_text: str) -> bool:
        """Validate the provided lambda function text."""
        # Return False if the lambda function does not start with 'lambda' or does not contain a colon
        return lambda_text.strip().startswith("lambda") and ":" in lambda_text

    async def filter_data(self) -> list[Data]:
        self.log(str(self.data))
        data = self.data[0].data if isinstance(self.data, list) else self.data.data

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
        processed_data = fn(data)

        # If it's a dict, wrap it in a Data object
        if isinstance(processed_data, dict):
            return [Data(**processed_data)]
        # If it's a list, convert each item to a Data object
        if isinstance(processed_data, list):
            return [Data(**item) if isinstance(item, dict) else Data(text=str(item)) for item in processed_data]
        # If it's anything else, convert to string and wrap in a Data object
        return [Data(text=str(processed_data))]
