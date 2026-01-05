import asyncio
import json
from contextlib import suppress
from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import ChatOllama

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.helpers.base_model import build_model_from_schema
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    SliderInput,
    TableInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.table import EditMode
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200
TABLE_ROW_PLACEHOLDER = {"name": "field", "description": "description of field", "type": "str", "multiple": "False"}


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"
    name = "OllamaModel"

    # Define constants for JSON keys
    JSON_MODELS_KEY = "models"
    JSON_NAME_KEY = "name"
    JSON_CAPABILITIES_KEY = "capabilities"
    DESIRED_CAPABILITY = "completion"
    TOOL_CALLING_CAPABILITY = "tools"

    # Define the table schema for the format input
    TABLE_SCHEMA = [
        {
            "name": "name",
            "display_name": "Name",
            "type": "str",
            "description": "Specify the name of the output field.",
            "default": "field",
            "edit_mode": EditMode.INLINE,
        },
        {
            "name": "description",
            "display_name": "Description",
            "type": "str",
            "description": "Describe the purpose of the output field.",
            "default": "description of field",
            "edit_mode": EditMode.POPOVER,
        },
        {
            "name": "type",
            "display_name": "Type",
            "type": "str",
            "edit_mode": EditMode.INLINE,
            "description": ("Indicate the data type of the output field (e.g., str, int, float, bool, dict)."),
            "options": ["str", "int", "float", "bool", "dict"],
            "default": "str",
        },
        {
            "name": "multiple",
            "display_name": "As List",
            "type": "boolean",
            "description": "Set to True if this output field should be a list of the specified type.",
            "edit_mode": EditMode.INLINE,
            "options": ["True", "False"],
            "default": "False",
        },
    ]
    default_table_row = {row["name"]: row.get("default", None) for row in TABLE_SCHEMA}
    default_table_row_schema = build_model_from_schema([default_table_row]).model_json_schema()

    inputs = [
        MessageTextInput(
            name="base_url",
            display_name="Ollama API URL",
            info="Endpoint of the Ollama API. Defaults to http://localhost:11434.",
            value="http://localhost:11434",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            info="Refer to https://ollama.com/library for more models.",
            refresh_button=True,
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Ollama API Key",
            info="Your Ollama API key.",
            value=None,
            required=False,
            real_time_refresh=True,
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        TableInput(
            name="format",
            display_name="Format",
            info="Specify the format of the output.",
            table_schema=TABLE_SCHEMA,
            value=default_table_row,
            show=False,
        ),
        DictInput(name="metadata", display_name="Metadata", info="Metadata to add to the run trace.", advanced=True),
        DropdownInput(
            name="mirostat",
            display_name="Mirostat",
            options=["Disabled", "Mirostat", "Mirostat 2.0"],
            info="Enable/disable Mirostat sampling for controlling perplexity.",
            value="Disabled",
            advanced=True,
            real_time_refresh=True,
        ),
        FloatInput(
            name="mirostat_eta",
            display_name="Mirostat Eta",
            info="Learning rate for Mirostat algorithm. (Default: 0.1)",
            advanced=True,
        ),
        FloatInput(
            name="mirostat_tau",
            display_name="Mirostat Tau",
            info="Controls the balance between coherence and diversity of the output. (Default: 5.0)",
            advanced=True,
        ),
        IntInput(
            name="num_ctx",
            display_name="Context Window Size",
            info="Size of the context window for generating tokens. (Default: 2048)",
            advanced=True,
        ),
        IntInput(
            name="num_gpu",
            display_name="Number of GPUs",
            info="Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
            advanced=True,
        ),
        IntInput(
            name="num_thread",
            display_name="Number of Threads",
            info="Number of threads to use during computation. (Default: detected for optimal performance)",
            advanced=True,
        ),
        IntInput(
            name="repeat_last_n",
            display_name="Repeat Last N",
            info="How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
            advanced=True,
        ),
        FloatInput(
            name="repeat_penalty",
            display_name="Repeat Penalty",
            info="Penalty for repetitions in generated text. (Default: 1.1)",
            advanced=True,
        ),
        FloatInput(name="tfs_z", display_name="TFS Z", info="Tail free sampling value. (Default: 1)", advanced=True),
        IntInput(name="timeout", display_name="Timeout", info="Timeout for the request stream.", advanced=True),
        IntInput(
            name="top_k", display_name="Top K", info="Limits token selection to top K. (Default: 40)", advanced=True
        ),
        FloatInput(name="top_p", display_name="Top P", info="Works together with top-k. (Default: 0.9)", advanced=True),
        BoolInput(
            name="enable_verbose_output",
            display_name="Ollama Verbose Output",
            info="Whether to print out response text.",
            advanced=True,
        ),
        MessageTextInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated list of tags to add to the run trace.",
            advanced=True,
        ),
        MessageTextInput(
            name="stop_tokens",
            display_name="Stop Tokens",
            info="Comma-separated list of tokens to signal the model to stop generating text.",
            advanced=True,
        ),
        MessageTextInput(
            name="system", display_name="System", info="System to use for generating text.", advanced=True
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Tool Model Enabled",
            info="Whether to enable tool calling in the model.",
            value=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="template", display_name="Template", info="Template to use for generating text.", advanced=True
        ),
        BoolInput(
            name="enable_structured_output",
            display_name="Enable Structured Output",
            info="Whether to enable structured output in the model.",
            value=False,
            advanced=False,
            real_time_refresh=True,
        ),
        *LCModelComponent.get_base_inputs(),
    ]

    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
        Output(display_name="Data", name="data_output", method="build_data_output"),
        Output(display_name="DataFrame", name="dataframe_output", method="build_dataframe_output"),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # Mapping mirostat settings to their corresponding values
        mirostat_options = {"Mirostat": 1, "Mirostat 2.0": 2}

        # Default to None for 'Disabled'
        mirostat_value = mirostat_options.get(self.mirostat, None)

        # Set mirostat_eta and mirostat_tau to None if mirostat is disabled
        if mirostat_value is None:
            mirostat_eta = None
            mirostat_tau = None
        else:
            mirostat_eta = self.mirostat_eta
            mirostat_tau = self.mirostat_tau

        transformed_base_url = transform_localhost_url(self.base_url)

        # Check if URL contains /v1 suffix (OpenAI-compatible mode)
        if transformed_base_url and transformed_base_url.rstrip("/").endswith("/v1"):
            # Strip /v1 suffix and log warning
            transformed_base_url = transformed_base_url.rstrip("/").removesuffix("/v1")
            logger.warning(
                "Detected '/v1' suffix in base URL. The Ollama component uses the native Ollama API, "
                "not the OpenAI-compatible API. The '/v1' suffix has been automatically removed. "
                "If you want to use the OpenAI-compatible API, please use the OpenAI component instead. "
                "Learn more at https://docs.ollama.com/openai#openai-compatibility"
            )

        try:
            output_format = self._parse_format_field(self.format) if self.enable_structured_output else None
        except Exception as e:
            msg = f"Failed to parse the format field: {e}"
            raise ValueError(msg) from e

        # Mapping system settings to their corresponding values
        llm_params = {
            "base_url": transformed_base_url,
            "model": self.model_name,
            "mirostat": mirostat_value,
            "format": output_format or None,
            "metadata": self.metadata,
            "tags": self.tags.split(",") if self.tags else None,
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": self.num_ctx or None,
            "num_gpu": self.num_gpu or None,
            "num_thread": self.num_thread or None,
            "repeat_last_n": self.repeat_last_n or None,
            "repeat_penalty": self.repeat_penalty or None,
            "temperature": self.temperature or None,
            "stop": self.stop_tokens.split(",") if self.stop_tokens else None,
            "system": self.system,
            "tfs_z": self.tfs_z or None,
            "timeout": self.timeout or None,
            "top_k": self.top_k or None,
            "top_p": self.top_p or None,
            "verbose": self.enable_verbose_output or False,
            "template": self.template,
        }
        headers = self.headers
        if headers is not None:
            llm_params["client_kwargs"] = {"headers": headers}

        # Remove parameters with None values
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. "
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again."
            )
            raise ValueError(msg) from e

        return output

    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                url = transform_localhost_url(url)
                if not url:
                    return False
                # Strip /v1 suffix if present, as Ollama API endpoints are at root level
                url = url.rstrip("/").removesuffix("/v1")
                if not url.endswith("/"):
                    url = url + "/"
                return (
                    await client.get(url=urljoin(url, "api/tags"), headers=self.headers)
                ).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name == "enable_structured_output":  # bind enable_structured_output boolean to format show value
            build_config["format"]["show"] = field_value

        if field_name == "mirostat":
            if field_value == "Disabled":
                build_config["mirostat_eta"]["advanced"] = True
                build_config["mirostat_tau"]["advanced"] = True
                build_config["mirostat_eta"]["value"] = None
                build_config["mirostat_tau"]["value"] = None

            else:
                build_config["mirostat_eta"]["advanced"] = False
                build_config["mirostat_tau"]["advanced"] = False

                if field_value == "Mirostat 2.0":
                    build_config["mirostat_eta"]["value"] = 0.2
                    build_config["mirostat_tau"]["value"] = 10
                else:
                    build_config["mirostat_eta"]["value"] = 0.1
                    build_config["mirostat_tau"]["value"] = 5

        if field_name in {"model_name", "base_url", "tool_model_enabled"}:
            logger.warning(f"Fetching Ollama models from updated URL: {build_config['base_url']}")

            if await self.is_valid_ollama_url(self.base_url):
                tool_model_enabled = build_config["tool_model_enabled"].get("value", False) or self.tool_model_enabled
                build_config["model_name"]["options"] = await self.get_models(
                    self.base_url, tool_model_enabled=tool_model_enabled
                )
            else:
                build_config["model_name"]["options"] = []
        if field_name == "keep_alive_flag":
            if field_value == "Keep":
                build_config["keep_alive"]["value"] = "-1"
                build_config["keep_alive"]["advanced"] = True
            elif field_value == "Immediately":
                build_config["keep_alive"]["value"] = "0"
                build_config["keep_alive"]["advanced"] = True
            else:
                build_config["keep_alive"]["advanced"] = False

        return build_config

    async def get_models(self, base_url_value: str, *, tool_model_enabled: bool | None = None) -> list[str]:
        """Fetches a list of models from the Ollama API that do not have the "embedding" capability.

        Args:
            base_url_value (str): The base URL of the Ollama API.
            tool_model_enabled (bool | None, optional): If True, filters the models further to include
                only those that support tool calling. Defaults to None.

        Returns:
            list[str]: A list of model names that do not have the "embedding" capability. If
                `tool_model_enabled` is True, only models supporting tool calling are included.

        Raises:
            ValueError: If there is an issue with the API request or response, or if the model
                names cannot be retrieved.
        """
        try:
            # Strip /v1 suffix if present, as Ollama API endpoints are at root level
            base_url = base_url_value.rstrip("/").removesuffix("/v1")
            if not base_url.endswith("/"):
                base_url = base_url + "/"
            base_url = transform_localhost_url(base_url)

            # Ollama REST API to return models
            tags_url = urljoin(base_url, "api/tags")

            # Ollama REST API to return model capabilities
            show_url = urljoin(base_url, "api/show")

            async with httpx.AsyncClient() as client:
                headers = self.headers
                # Fetch available models
                tags_response = await client.get(url=tags_url, headers=headers)
                tags_response.raise_for_status()
                models = tags_response.json()
                if asyncio.iscoroutine(models):
                    models = await models
                await logger.adebug(f"Available models: {models}")

                # Filter models that are NOT embedding models
                model_ids = []
                for model in models[self.JSON_MODELS_KEY]:
                    model_name = model[self.JSON_NAME_KEY]
                    await logger.adebug(f"Checking model: {model_name}")

                    payload = {"model": model_name}
                    show_response = await client.post(url=show_url, json=payload, headers=headers)
                    show_response.raise_for_status()
                    json_data = show_response.json()
                    if asyncio.iscoroutine(json_data):
                        json_data = await json_data

                    capabilities = json_data.get(self.JSON_CAPABILITIES_KEY, [])
                    await logger.adebug(f"Model: {model_name}, Capabilities: {capabilities}")

                    if self.DESIRED_CAPABILITY in capabilities and (
                        not tool_model_enabled or self.TOOL_CALLING_CAPABILITY in capabilities
                    ):
                        model_ids.append(model_name)

        except (httpx.RequestError, ValueError) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e

        return model_ids

    def _parse_format_field(self, format_value: Any) -> Any:
        """Parse the format field to handle both string and dict inputs.

        The format field can be:
        - A simple string like "json" (backward compatibility)
        - A JSON string from NestedDictInput that needs parsing
        - A dict/JSON schema (already parsed)
        - None or empty

        Args:
            format_value: The raw format value from the input field

        Returns:
            Parsed format value as string, dict, or None
        """
        if not format_value:
            return None

        schema = format_value
        if isinstance(format_value, list):
            schema = build_model_from_schema(format_value).model_json_schema()
            if schema == self.default_table_row_schema:
                return None  # the rows are generic placeholder rows
        elif isinstance(format_value, str):  # parse as json if string
            with suppress(json.JSONDecodeError):  # e.g., literal "json" is valid for format field
                schema = json.loads(format_value)

        return schema or None

    async def _parse_json_response(self) -> Any:
        """Parse the JSON response from the model.

        This method gets the text response and attempts to parse it as JSON.
        Works with models that have format='json' or a JSON schema set.

        Returns:
            Parsed JSON (dict, list, or primitive type)

        Raises:
            ValueError: If the response is not valid JSON
        """
        message = await self.text_response()
        text = message.text if hasattr(message, "text") else str(message)

        if not text:
            msg = "No response from model"
            raise ValueError(msg)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON response. Ensure model supports JSON output. Error: {e}"
            raise ValueError(msg) from e

    async def build_data_output(self) -> Data:
        """Build a Data output from the model's JSON response.

        Returns:
            Data: A Data object containing the parsed JSON response
        """
        parsed = await self._parse_json_response()

        # If the response is already a dict, wrap it in Data
        if isinstance(parsed, dict):
            return Data(data=parsed)

        # If it's a list, wrap in a results container
        if isinstance(parsed, list):
            if len(parsed) == 1:
                return Data(data=parsed[0])
            return Data(data={"results": parsed})

        # For primitive types, wrap in a value container
        return Data(data={"value": parsed})

    async def build_dataframe_output(self) -> DataFrame:
        """Build a DataFrame output from the model's JSON response.

        Returns:
            DataFrame: A DataFrame containing the parsed JSON response

        Raises:
            ValueError: If the response cannot be converted to a DataFrame
        """
        parsed = await self._parse_json_response()

        # If it's a list of dicts, convert directly to DataFrame
        if isinstance(parsed, list):
            if not parsed:
                return DataFrame()
            # Ensure all items are dicts for proper DataFrame conversion
            if all(isinstance(item, dict) for item in parsed):
                return DataFrame(parsed)
            msg = "List items must be dictionaries to convert to DataFrame"
            raise ValueError(msg)

        # If it's a single dict, wrap in a list to create a single-row DataFrame
        if isinstance(parsed, dict):
            return DataFrame([parsed])

        # For primitive types, create a single-column DataFrame
        return DataFrame([{"value": parsed}])

    @property
    def headers(self) -> dict[str, str] | None:
        """Get the headers for the Ollama API."""
        if self.api_key and self.api_key.strip():
            return {"Authorization": f"Bearer {self.api_key}"}
        return None
