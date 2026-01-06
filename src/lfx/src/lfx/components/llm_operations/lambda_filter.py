from __future__ import annotations

import json
import re
from collections.abc import Callable  # noqa: TC003 - required at runtime for dynamic exec()
from typing import Any

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

TEXT_TRANSFORM_PROMPT = (
    "Given this text, create a Python lambda function that transforms it "
    "according to the instruction.\n"
    "The lambda should take a string parameter and return the transformed string.\n\n"
    "Text Preview:\n{text_preview}\n\n"
    "Instruction: {instruction}\n\n"
    "Return ONLY the lambda function and nothing else. No need for ```python or whatever.\n"
    "Just a string starting with lambda.\n"
    "Example: lambda text: text.upper()"
)

DATA_TRANSFORM_PROMPT = (
    "Given this data structure and examples, create a Python lambda function "
    "that implements the following instruction:\n\n"
    "Data Structure:\n{dump_structure}\n\n"
    "Example Items:\n{data_sample}\n\n"
    "Instruction: {instruction}\n\n"
    "Return ONLY the lambda function and nothing else. No need for ```python or whatever.\n"
    "Just a string starting with lambda."
)


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

    def _extract_message_text(self) -> str:
        """Extract text content from Message input(s)."""
        if isinstance(self.data, Message):
            return self.data.text or ""

        texts = [msg.text or "" for msg in self.data if isinstance(msg, Message)]
        return "\n\n".join(texts) if len(texts) > 1 else (texts[0] if texts else "")

    def _extract_structured_data(self) -> dict | list:
        """Extract structured data from Data or DataFrame input(s)."""
        if isinstance(self.data, DataFrame):
            return self.data.to_dict(orient="records")

        if hasattr(self.data, "data"):
            return self.data.data

        if not isinstance(self.data, list):
            return self.data

        combined_data: list[dict] = []
        for item in self.data:
            if isinstance(item, DataFrame):
                combined_data.extend(item.to_dict(orient="records"))
            elif hasattr(item, "data"):
                if isinstance(item.data, dict):
                    combined_data.append(item.data)
                elif isinstance(item.data, list):
                    combined_data.extend(item.data)

        if len(combined_data) == 1 and isinstance(combined_data[0], dict):
            return combined_data[0]
        if len(combined_data) == 0:
            return {}
        return combined_data

    def _is_message_input(self) -> bool:
        """Check if input is Message type."""
        if isinstance(self.data, Message):
            return True
        return isinstance(self.data, list) and len(self.data) > 0 and isinstance(self.data[0], Message)

    def _build_text_prompt(self, text: str) -> str:
        """Build prompt for text/Message transformation."""
        text_length = len(text)
        if text_length > self.max_size:
            text_preview = (
                f"Text length: {text_length} characters\n\n"
                f"First {self.sample_size} characters:\n{text[: self.sample_size]}\n\n"
                f"Last {self.sample_size} characters:\n{text[-self.sample_size :]}"
            )
        else:
            text_preview = text

        return TEXT_TRANSFORM_PROMPT.format(text_preview=text_preview, instruction=self.filter_instruction)

    def _build_data_prompt(self, data: dict | list) -> str:
        """Build prompt for structured data transformation."""
        dump = json.dumps(data)
        dump_structure = json.dumps(self.get_data_structure(data))

        if len(dump) > self.max_size:
            data_sample = (
                f"Data is too long to display...\n\nFirst lines (head): {dump[: self.sample_size]}\n\n"
                f"Last lines (tail): {dump[-self.sample_size :]}"
            )
        else:
            data_sample = dump

        return DATA_TRANSFORM_PROMPT.format(
            dump_structure=dump_structure, data_sample=data_sample, instruction=self.filter_instruction
        )

    def _parse_lambda_from_response(self, response_text: str) -> Callable[[Any], Any]:
        """Extract and validate lambda function from LLM response."""
        lambda_match = re.search(r"lambda\s+\w+\s*:.*?(?=\n|$)", response_text)
        if not lambda_match:
            msg = f"Could not find lambda in response: {response_text}"
            raise ValueError(msg)

        lambda_text = lambda_match.group().strip()
        self.log(f"Generated lambda: {lambda_text}")

        if not self._validate_lambda(lambda_text):
            msg = f"Invalid lambda format: {lambda_text}"
            raise ValueError(msg)

        return eval(lambda_text)  # noqa: S307

    async def _execute_lambda(self) -> Any:
        """Generate and execute a lambda function based on input type."""
        if self._is_message_input():
            data: Any = self._extract_message_text()
            prompt = self._build_text_prompt(data)
        else:
            data = self._extract_structured_data()
            prompt = self._build_data_prompt(data)

        llm = get_llm(model=self.model, user_id=self.user_id, api_key=self.api_key)
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        fn = self._parse_lambda_from_response(response_text)
        return fn(data)

    def _handle_process_error(self, error: Exception, output_type: str) -> None:
        """Handle errors from process methods with context-aware messages."""
        input_type = self._get_input_type_name()
        error_msg = (
            f"Failed to convert result to {output_type} output. "
            f"Error: {error}. "
            f"Input type was {input_type}. "
            f"Try using the same output type as the input."
        )
        raise ValueError(error_msg) from error

    def _convert_result_to_data(self, result: Any) -> Data:
        """Convert lambda result to Data object."""
        if isinstance(result, dict):
            return Data(data=result)
        if isinstance(result, list):
            return Data(data={"_results": result})
        return Data(data={"text": str(result)})

    def _convert_result_to_dataframe(self, result: Any) -> DataFrame:
        """Convert lambda result to DataFrame object."""
        if isinstance(result, list):
            if all(isinstance(item, dict) for item in result):
                return DataFrame(result)
            return DataFrame([{"value": item} for item in result])
        if isinstance(result, dict):
            return DataFrame([result])
        return DataFrame([{"value": str(result)}])

    def _convert_result_to_message(self, result: Any) -> Message:
        """Convert lambda result to Message object."""
        if isinstance(result, str):
            return Message(text=result, sender=MESSAGE_SENDER_AI)
        if isinstance(result, list):
            text = "\n".join(str(item) for item in result)
            return Message(text=text, sender=MESSAGE_SENDER_AI)
        if isinstance(result, dict):
            text = json.dumps(result, indent=2)
            return Message(text=text, sender=MESSAGE_SENDER_AI)
        return Message(text=str(result), sender=MESSAGE_SENDER_AI)

    async def process_as_data(self) -> Data:
        """Process the data and return as a Data object."""
        try:
            result = await self._execute_lambda()
            return self._convert_result_to_data(result)
        except Exception as e:  # noqa: BLE001 - dynamic lambda can raise any exception
            self._handle_process_error(e, "Data")

    async def process_as_dataframe(self) -> DataFrame:
        """Process the data and return as a DataFrame."""
        try:
            result = await self._execute_lambda()
            return self._convert_result_to_dataframe(result)
        except Exception as e:  # noqa: BLE001 - dynamic lambda can raise any exception
            self._handle_process_error(e, "DataFrame")

    async def process_as_message(self) -> Message:
        """Process the data and return as a Message."""
        try:
            result = await self._execute_lambda()
            return self._convert_result_to_message(result)
        except Exception as e:  # noqa: BLE001 - dynamic lambda can raise any exception
            self._handle_process_error(e, "Message")
