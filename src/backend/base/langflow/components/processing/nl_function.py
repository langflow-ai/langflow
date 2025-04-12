from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from langflow.custom import Component
from langflow.io import (
    DataInput,
    HandleInput,
    MultilineInput,
    Output,
    BoolInput,
    StrInput,
    DictInput,
    IntInput,
)
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame
from langflow.utils.data_structure import get_data_structure
from langflow.utils.llm.nlf import backend

if TYPE_CHECKING:
    from collections.abc import Callable


class NLFunctionComponent(Component):
    display_name = "Natural Language Function"
    description = "Uses an LLM to generate and execute functions based on natural language instructions."
    icon = "function"
    name = "NLFunction"
    beta = True

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to process using the generated function.",
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
            name="instruction",
            display_name="Function Instructions",
            info="Natural language instructions for the function to generate. Example: 'Create a function that filters items where status is active'",
            value="Create a function that...",
            required=True,
        ),
        StrInput(
            name="system_prompt",
            display_name="System Prompt",
            info="Optional system prompt to guide the LLM's behavior.",
            value="You are a helpful assistant that generates Python functions.",
            advanced=True,
        ),
        BoolInput(
            name="debug",
            display_name="Debug Mode",
            info="Enable to include debug information in the output.",
            value=False,
            advanced=True,
        ),
        DictInput(
            name="llm_kwargs",
            display_name="LLM Parameters",
            info="Additional parameters to pass to the LLM (e.g., temperature, max_tokens).",
            value={},
            advanced=True,
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
            display_name="Processed Data",
            name="processed_data",
            method="process_data",
        ),
        Output(
            display_name="Generated Function",
            name="function_code",
            method="get_function_code",
        ),
        Output(
            display_name="Debug Info",
            name="debug_info",
            method="get_debug_info",
        ),
        Output(
            display_name="DataFrame",
            name="dataframe",
            method="as_dataframe",
        ),
    ]

    def __init__(self):
        super().__init__()
        self._generated_function = None
        self._debug_info = None

    def get_data_structure(self, data):
        """Extract the structure of a dictionary, replacing values with their types."""
        return {k: get_data_structure(v) for k, v in data.items()}

    def _validate_function(self, function_text: str) -> bool:
        """Validate the provided function text."""
        # Check if it starts with 'def' and has proper indentation
        lines = function_text.strip().split("\n")
        return (
            lines[0].strip().startswith("def")
            and all(line.startswith("    ") for line in lines[1:])
        )

    @backend(model=None)  # Will be set in process_data
    def _generate_function(self, instruction: str, data_structure: dict, data_sample: str) -> str:
        """Generate a Python function based on the instructions and data structure.
        
        This function is decorated with @backend to use the LLM for function generation.
        The actual model will be replaced with the one provided in the component inputs.
        """
        return f'''Generate a Python function based on the following instructions:
        {instruction}

        The function should work with data that has this structure:
        {json.dumps(data_structure, indent=2)}

        Example data:
        {data_sample}

        Return only the function definition, starting with 'def' and ending with the function body.
        Do not include any additional text or explanations.
        The function should take a single argument (the data) and return the processed result.
        '''

    async def process_data(self) -> list[Data]:
        """Process the input data using the generated function."""
        self.log(str(self.data))
        data = self.data

        # Prepare data for function generation
        data_structure = self.get_data_structure(data)
        data_dump = json.dumps(data)
        
        # Handle large datasets
        if len(data_dump) > self.max_size:
            data_sample = (
                f"Data is too long to display... \n\n First lines (head): {data_dump[:self.sample_size]} \n\n"
                f" Last lines (tail): {data_dump[-self.sample_size:]})"
            )
        else:
            data_sample = data_dump

        # Create a new backend instance with the provided LLM
        backend_instance = backend(
            model=self.llm,
            system=self.system_prompt,
            debug=self.debug,
            **self.llm_kwargs
        )
        
        # Generate the function using the backend
        function_code = await backend_instance.run(
            self._generate_function,
            self.instruction,
            data_structure,
            data_sample
        )
        
        # Validate the function
        if not self._validate_function(function_code):
            msg = f"Invalid function format: {function_code}"
            raise ValueError(msg)

        # Store the generated function and debug info
        self._generated_function = function_code
        if self.debug:
            self._debug_info = {
                "function_code": function_code,
                "data_structure": data_structure,
                "data_sample": data_sample,
                "instruction": self.instruction,
            }

        # Create and execute the function
        local_vars = {}
        exec(function_code, {}, local_vars)
        generated_function = local_vars[list(local_vars.keys())[-1]]
        
        # Apply the function to the data
        processed_data = generated_function(data)
        
        # Convert to Data objects
        if isinstance(processed_data, dict):
            return [Data(**processed_data)]
        if isinstance(processed_data, list):
            return [Data(**item) if isinstance(item, dict) else Data(text=str(item)) for item in processed_data]
        return [Data(text=str(processed_data))]

    def get_function_code(self) -> str:
        """Return the generated function code."""
        if not self._generated_function:
            return ""
        return self._generated_function

    def get_debug_info(self) -> dict:
        """Return debug information if debug mode is enabled."""
        if not self.debug or not self._debug_info:
            return {}
        return self._debug_info

    async def as_dataframe(self) -> DataFrame:
        """Return processed data as a DataFrame."""
        processed_data = await self.process_data()
        return DataFrame(processed_data) 