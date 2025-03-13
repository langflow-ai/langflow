from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List
import json
import re
from loguru import logger

from langflow.custom import Component
from langflow.io import DataInput, HandleInput, MultilineInput, IntInput
from langflow.io import Output
from langflow.schema import Data
from langflow.utils.data_structure import get_data_structure

# if TYPE_CHECKING:
#     from langchain_core.runnables import Runnable

class LambdaFilterComponent(Component):
    display_name = "Lambda Filter"
    description = "Uses an LLM to generate a lambda function for filtering or transforming structured data."
    icon = "filter"
    name = "LambdaFilter"
    beta = True

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
            display_name="Lambda Instruction",
            info="Natural language instruction for how to filter or transform the data using a lambda function.",
            value="Filter or transform the data to...",
            required=True,
        ),
        IntInput(
            name="sample_size",
            display_name="Sample Size",
            info="For large datasets, number of items to sample from head/tail.",
            value=1000,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Processed Data",
            name="filtered_data",
            method="filter_data",
        ),
    ]
    
    def get_data_structure(self, data):
        """Extract the structure of a dictionary, replacing values with their types."""
        return {k: get_data_structure(v) for k, v in data.items()}

    def _validate_lambda(self, lambda_text: str) -> bool:
        # """Validate that the lambda follows the required format"""
        # # Must start with 'lambda x:'
        # if not lambda_text.startswith('lambda x:'):
        #     return False
        
        # Check for disallowed patterns
        # if (
        #     re.search(r'\[.*for.*in.*\]', lambda_text) or  # List comprehension
        #     re.search(r'\.map\s*\(', lambda_text) or       # .map() function
        #     re.search(r'\.filter\s*\(', lambda_text) or    # .filter() function
        #     ';' in lambda_text or                          # Multiple statements
        #     re.search(r'\[[\'"][^\]]*[\'"]\]', lambda_text) or  # String-based list indexing
        #     re.search(r'\[[a-zA-Z_][a-zA-Z0-9_]*\]', lambda_text)  # Variable-based list indexing
        # ):
        #     return False
        
        # # Allow numeric list indexing when used with .get()
        # list_index_matches = re.finditer(r'\[[0-9]+\]', lambda_text)
        # for match in list_index_matches:
        #     # Look behind for .get() with any default value
        #     start = max(0, match.start() - 50)  # Look at most 50 chars behind
        #     preceding_text = lambda_text[start:match.start()]
        #     if not re.search(r'\.get\s*\([^)]+\)', preceding_text):
        #         return False
            
        return True

    async def filter_data(self) -> list[Data]:
        # Validate inputs first
        # self._validate_inputs({})
        
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
        if len(dump) > 100000:
            data_sample = f"Data is too long to display... \n\n First lines (head): {dump[:sample_size]} \n\n Last lines (tail): {dump[-sample_size:]}"
        else:
            data_sample = dump

        self.log(data_sample)
        
        prompt = f'''Given this data structure and examples, create a Python lambda function that implements the following instruction:

Data Structure:
{dump_structure}

Example Items:
{data_sample}

Instruction: {instruction}

Return ONLY the lambda function and nothing else. No need for ```python or whatever. Just a string starting with lambda.
'''

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        self.log(response_text)
        
        # Extract lambda using regex
        lambda_match = re.search(r'lambda\s+\w+\s*:.*?(?=\n|$)', response_text)
        if not lambda_match:
            raise ValueError(f"Could not find lambda in response: {response_text}")
            
        lambda_text = lambda_match.group().strip()
        self.log(lambda_text)

        # Validation is commented out as requested
        if not self._validate_lambda(lambda_text):
            raise ValueError(f"Invalid lambda format: {lambda_text}")
        
        # Create and apply the function
        fn: Callable[[Any], Any] = eval(lambda_text)
        
        # Apply the lambda function to the data
        processed_data = fn(data)
            
        return processed_data 