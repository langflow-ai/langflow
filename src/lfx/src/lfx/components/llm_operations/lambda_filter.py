from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, ModelInput, MultilineInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from collections.abc import Callable

# # Compute model options once at module level
# _MODEL_OPTIONS = get_language_model_options()
# _PROVIDERS = [provider["provider"] for provider in _MODEL_OPTIONS]


class LambdaFilterComponent(Component):
    display_name = "Smart Transform"
    description = "Uses an LLM to generate a function for filtering or transforming structured data and messages."
    documentation: str = "https://docs.langflow.org/smart-transform"
    icon = "square-function"
    name = "Smart Transform"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The structured data or text messages to filter or transform using a lambda function.",
            input_types=["Data", "DataFrame", "Message"],
            is_list=True,
            required=True,
        ),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        MultilineInput(
            name="filter_instruction",
            display_name="Instructions",
            info=(
                "Natural language instructions for how to filter or transform the data using a lambda function. "
                "Examples: 'Filter the data to only include items where status is active', "
                "'Convert the text to uppercase', 'Keep only first 100 characters'"
            ),
            value="Transform the data to...",
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
        Output(
            display_name="Output",
            name="message_output",
            method="process_as_message",
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

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

    def _get_input_type_name(self) -> str:
        """Detect and return the input type name for error messages."""
        if isinstance(self.data, Message):
            return "Message"
        if isinstance(self.data, DataFrame):
            return "DataFrame"
        if isinstance(self.data, Data):
            return "Data"
        if isinstance(self.data, list) and len(self.data) > 0:
            first = self.data[0]
            if isinstance(first, Message):
                return "Message"
            if isinstance(first, DataFrame):
                return "DataFrame"
            if isinstance(first, Data):
                return "Data"
        return "unknown"

    async def _execute_lambda(self) -> Any:
        # Handle Message input specifically
        is_message_input = False

        # Check if input is a Message (single or list)
        if isinstance(self.data, Message):
            is_message_input = True
            data = self.data.text or ""
        elif isinstance(self.data, list) and len(self.data) > 0 and isinstance(self.data[0], Message):
            is_message_input = True
            # For list of Messages, combine their texts
            texts = [msg.text or "" for msg in self.data if isinstance(msg, Message)]
            data = "\n\n".join(texts) if len(texts) > 1 else (texts[0] if texts else "")
        # Convert input to a unified format
        elif isinstance(self.data, list):
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

        llm = get_llm(model=self.model, user_id=self.user_id, api_key=self.api_key)
        instruction = self.filter_instruction
        sample_size = self.sample_size

        # Different handling for Message vs structured data
        if is_message_input:
            # For text/Message input, create a text-specific prompt
            text_length = len(data) if isinstance(data, str) else 0
            self.log(f"Text length: {text_length}")

            # For large text, show only preview
            if text_length > self.max_size:
                text_preview = (
                    f"Text length: {text_length} characters\n\n"
                    f"First {sample_size} characters:\n{data[:sample_size]}\n\n"
                    f"Last {sample_size} characters:\n{data[-sample_size:]}"
                )
            else:
                text_preview = data

            self.log(text_preview)

            prompt = f"""Given this text, create a Python lambda function that transforms it according to the instruction.
The lambda should take a string parameter and return the transformed string.

Text Preview:
{text_preview}

Instruction: {instruction}

Return ONLY the lambda function and nothing else. No need for ```python or whatever.
Just a string starting with lambda.
Example: lambda text: text.upper()
"""
        else:
            # Original structured data handling
            dump = json.dumps(data)

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
        try:
            result = await self._execute_lambda()

            # Convert result to Data based on type
            if isinstance(result, dict):
                return Data(data=result)
            if isinstance(result, list):
                return Data(data={"_results": result})
            # For other types, convert to string
            return Data(data={"text": str(result)})

        except Exception as e:
            input_type = self._get_input_type_name()
            error_msg = (
                f"Failed to convert result to Data output. "
                f"Error: {e}. "
                f"Input type was {input_type}. "
                f"Try using the same output type as the input."
            )
            self.log(f"Error in process_as_data: {error_msg}")
            raise ValueError(error_msg) from e

    async def process_as_dataframe(self) -> DataFrame:
        """Process the data and return as a DataFrame."""
        try:
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

        except Exception as e:
            input_type = self._get_input_type_name()
            error_msg = (
                f"Failed to convert result to DataFrame output. "
                f"Error: {e}. "
                f"Input type was {input_type}. "
                f"Try using the same output type as the input."
            )
            self.log(f"Error in process_as_dataframe: {error_msg}")
            raise ValueError(error_msg) from e

    async def process_as_message(self) -> Message:
        """Process the data and return as a Message."""
        try:
            result = await self._execute_lambda()

            # Convert result to Message based on type
            if isinstance(result, str):
                # String result becomes message text
                return Message(text=result, sender=MESSAGE_SENDER_AI)
            if isinstance(result, list):
                # List converted to joined string
                text = "\n".join(str(item) for item in result)
                return Message(text=text, sender=MESSAGE_SENDER_AI)
            if isinstance(result, dict):
                # Dict converted to formatted string
                text = json.dumps(result, indent=2)
                return Message(text=text, sender=MESSAGE_SENDER_AI)
            # Other types: convert to string
            return Message(text=str(result), sender=MESSAGE_SENDER_AI)

        except Exception as e:
            input_type = self._get_input_type_name()
            error_msg = (
                f"Failed to convert result to Message output. "
                f"Error: {e}. "
                f"Input type was {input_type}. "
                f"Try using the same output type as the input."
            )
            self.log(f"Error in process_as_message: {error_msg}")
            raise ValueError(error_msg) from e
