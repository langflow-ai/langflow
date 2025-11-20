import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

import aiohttp
from langchain_core.tools import StructuredTool
from langflow.base.data.base_file import BaseFileComponent
from langflow.custom.custom_component.split_to_page import BasePageSplitterComponent
from langflow.inputs.inputs import HandleInput
from pydantic import ValidationError

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.base.agents.events import ExceptionWithMessageError
from langflow.base.models.model_input_constants import (
    ALL_PROVIDER_FIELDS,
    MODEL_DYNAMIC_UPDATE_FIELDS,
    MODEL_PROVIDERS_DICT,
    MODELS_METADATA,
)
from langflow.base.models.model_utils import get_model_name
from langflow.components.helpers.current_date import CurrentDateComponent
from langflow.components.helpers.memory import MemoryComponent
from langflow.components.langchain_utilities.tool_calling import (
    ToolCallingAgentComponent,
)
from langflow.custom.custom_component.component import _get_component_toolkit
from langflow.custom.utils import update_component_build_config
from langflow.field_typing import Tool
from langflow.helpers.base_model import build_model_from_schema
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MultilineInput,
    Output,
    TableInput,
)
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from langflow.schema.table import EditMode
from langflow.custom.default_providers import apply_provider_defaults
from typing import Any


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "Google Generative AI", "OpenAI", "Azure OpenAI"]


class AgentComponent(ToolCallingAgentComponent, BaseFileComponent):
    display_name: str = "Agent"
    description: str = (
        "Define the agent's instructions, then enter a task to complete using tools."
    )
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = False
    name = "Agent"

    memory_inputs = [
        set_advanced_true(component_input)
        for component_input in MemoryComponent().inputs
    ]

    # Filter out json_mode from OpenAI inputs since we handle structured output differently
    if "OpenAI" in MODEL_PROVIDERS_DICT:
        openai_inputs_filtered = [
            input_field
            for input_field in MODEL_PROVIDERS_DICT["OpenAI"]["inputs"]
            if not (hasattr(input_field, "name") and input_field.name == "json_mode")
        ]
    else:
        openai_inputs_filtered = []

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*MODEL_PROVIDERS_LIST],
            value="OpenAI",
            real_time_refresh=True,
            refresh_button=False,
            input_types=[],
            options_metadata=[
                MODELS_METADATA[key]
                for key in MODEL_PROVIDERS_LIST
                if key in MODELS_METADATA
            ]
            + [{"icon": "brain"}],
            external_options={
                "fields": {
                    "data": {
                        "node": {
                            "name": "connect_other_models",
                            "display_name": "Connect other models",
                            "icon": "CornerDownLeft",
                        }
                    }
                },
            },
        ),
        *openai_inputs_filtered,
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Chat History Messages",
            value=100,
            info="Number of chat history messages to retrieve.",
            advanced=True,
            show=True,
        ),
        MultilineInput(
            name="format_instructions",
            display_name="Output Format Instructions",
            info="Generic Template for structured output formatting. Valid only with Structured response.",
            value=(
                "You are an AI that extracts structured JSON objects from unstructured text. "
                "Use a predefined schema with expected types (str, int, float, bool, dict). "
                "Extract ALL relevant instances that match the schema - if multiple patterns exist, capture them all. "
                "Fill missing or ambiguous values with defaults: null for missing values. "
                "Remove exact duplicates but keep variations that have different field values. "
                "Always return valid JSON in the expected format, never throw errors. "
                "If multiple objects can be extracted, return them all in the structured format."
            ),
            advanced=True,
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "file_path"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "silent_errors"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "delete_server_file_after_processing"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "ignore_unsupported_extensions"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "ignore_unspecified_files"
        ),
        BoolInput(
            name="split_pdf_to_images",
            display_name="Split PDF to Images",
            value=True,
            info="If enabled, automatically split PDF files into individual page images before sending to the agent",
            advanced=True,
        ),
        BoolInput(
            name="keep_original_size",
            display_name="Keep Original Image Size",
            value=True,
            info="Keep the original image size when splitting PDFs",
            advanced=True,
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info=(
                "Schema Validation: Define the structure and data types for structured output. "
                "No validation if no output schema."
            ),
            advanced=True,
            required=False,
            value=[],
            table_schema=[
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
                    "description": (
                        "Indicate the data type of the output field (e.g., str, int, float, bool, dict)."
                    ),
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
        ),
        *LCToolsAgentComponent._base_inputs,
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    def __init__(self, **kwargs):
        super(BaseFileComponent, self).__init__(**kwargs)

        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}
        self._text_content = ""

        # Create an instance of the image splitter as a helper (composition)
        self._image_splitter = None

    def _get_image_splitter(self):
        """Lazy initialization of image splitter helper."""
        if self._image_splitter is None:
            from langflow.custom.custom_component.split_to_page import (
                BasePageSplitterComponent,
            )

            # Use the factory method with cleanup_on_exit=False
            # We'll handle cleanup manually in the agent
            self._image_splitter = BasePageSplitterComponent.create_helper(
                temp_dir=self.temp_dir,
                silent_errors=self.silent_errors,
                keep_original_size=self.keep_original_size,
                cleanup_on_exit=False,  # Manual cleanup control
            )
        return self._image_splitter

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL."""
        try:
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                filename = "downloaded_file"

            local_path = os.path.join(self.temp_dir, filename)

            async with aiohttp.ClientSession() as session, session.get(url) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

            self._downloaded_files[url] = local_path
            logger.info(f"Successfully downloaded file to {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Error downloading file from URL: {e!s}")
            if not self.silent_errors:
                raise
            return None

    async def _validate_and_resolve_paths_async(
        self,
    ) -> list[BaseFileComponent.BaseFile]:
        """Handle URLs and local paths asynchronously."""
        resolved_files = []
        file_paths = self._file_path_as_list()

        for obj in file_paths:
            server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)

            if not server_file_path:
                if not self.ignore_unspecified_files:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    if not self.silent_errors:
                        raise ValueError(msg)
                continue

            try:
                paths_to_process = (
                    server_file_path
                    if isinstance(server_file_path, list)
                    else [server_file_path]
                )

                for path in paths_to_process:
                    try:
                        if isinstance(path, str) and path.startswith(
                            ("http://", "https://")
                        ):
                            local_path = await self._download_file_from_url(path)
                            if local_path:
                                file_obj = BaseFileComponent.BaseFile(
                                    data=obj,
                                    path=Path(local_path),
                                    delete_after_processing=True,
                                    silent_errors=self.silent_errors,
                                )
                                resolved_files.append(file_obj)
                        else:
                            path_obj = Path(path) if isinstance(path, str) else path
                            if path_obj.exists():
                                file_obj = BaseFileComponent.BaseFile(
                                    data=obj,
                                    path=path_obj,
                                    delete_after_processing=self.delete_server_file_after_processing,
                                    silent_errors=self.silent_errors,
                                )
                                resolved_files.append(file_obj)
                            elif not self.silent_errors:
                                raise FileNotFoundError(f"File not found: {path}")

                    except Exception as e:
                        if not self.silent_errors:
                            raise
                        logger.error(f"Error processing path {path}: {e}")

            except Exception as e:
                if not self.silent_errors:
                    raise
                logger.error(f"Error processing file object: {e}")

        return resolved_files

    async def _process_pdf_files(
        self, files: list[BaseFileComponent.BaseFile]
    ) -> list[str]:
        """Process PDF files by splitting them into images if needed.

        Args:
            files: List of BaseFile objects

        Returns:
            List of file paths (either original or split image paths)
        """
        processed_paths = []

        # Get the image splitter helper
        splitter = self._get_image_splitter()

        for file_obj in files:
            file_path = file_obj.path
            ext = file_path.suffix.lower()

            # Check if it's a PDF and split_pdf_to_images is enabled
            if ext == ".pdf" and self.split_pdf_to_images:
                try:
                    logger.info(f"Splitting PDF to images: {file_path}")

                    # Use the helper's method to split PDF
                    image_bytes_list = await splitter._split_pdf_to_images(
                        str(file_path)
                    )

                    # Save images locally and collect paths
                    for i, image_bytes in enumerate(image_bytes_list):
                        filename = f"{file_path.stem}_page_{i + 1}.png"
                        local_path = await splitter._save_image_locally(
                            image_bytes, filename
                        )

                        # Extract actual path from file:// URL if present
                        if local_path.startswith("file://"):
                            local_path = local_path[7:]

                        processed_paths.append(local_path)
                        logger.info(f"Saved PDF page {i + 1} as image: {local_path}")

                except Exception as e:
                    logger.error(f"Error splitting PDF {file_path}: {e}")
                    if not self.silent_errors:
                        raise
                    # If splitting fails, use original PDF
                    processed_paths.append(str(file_path))
            else:
                # Not a PDF or splitting disabled, use original file
                processed_paths.append(str(file_path))

        return processed_paths

    async def get_agent_requirements(self):
        """Get the agent requirements for the agent."""
        llm_model, display_name = await self.get_llm()
        if llm_model is None:
            msg = "No language model selected. Please choose a model to proceed."
            raise ValueError(msg)
        self.model_name = get_model_name(llm_model, display_name=display_name)

        # Get memory data
        self.chat_history = await self.get_memory_data()
        if isinstance(self.chat_history, Message):
            self.chat_history = [self.chat_history]

        # Add current date tool if enabled
        if self.add_current_date_tool:
            if not isinstance(self.tools, list):
                self.tools = []
            current_date_tool = (
                await CurrentDateComponent(**self.get_base_args()).to_toolkit()
            ).pop(0)
            if not isinstance(current_date_tool, StructuredTool):
                msg = "CurrentDateComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            self.tools.append(current_date_tool)
        return llm_model, self.chat_history, self.tools

    async def message_response(self) -> Message:
        try:
            llm_model, self.chat_history, self.tools = (
                await self.get_agent_requirements()
            )
            files = await self._validate_and_resolve_paths_async()

            # Initialize input_dict
            input_dict = self.input_value.model_dump()
            if "files" not in input_dict or input_dict["files"] is None:
                input_dict["files"] = []

            self.log(f'Initial files: {input_dict["files"]}', "")

            # Process files (split PDFs if needed)
            if files:
                processed_file_paths = await self._process_pdf_files(files)

                # Debug logging
                logger.info(f"File paths to add: {processed_file_paths}")

                input_dict["files"].extend(processed_file_paths)
                logger.info(
                    f"Processed {len(files)} input files into {len(processed_file_paths)} file(s)"
                )

            # Debug logging
            logger.info(f"Final files list: {input_dict['files']}")

            # Recreate Message with updated files
            self.input_value = Message(**input_dict)
            self.log(f"Sending {len(input_dict['files'])} file(s) to agent", "")

            # Set up and run agent
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
            )
            agent = self.create_agent_runnable()
            result = await self.run_agent(agent)
            self._agent_result = result

        except (ValueError, TypeError, KeyError) as e:
            await logger.aerror(f"{type(e).__name__}: {e!s}")
            raise
        except ExceptionWithMessageError as e:
            await logger.aerror(f"ExceptionWithMessageError occurred: {e}")
            raise
        except Exception as e:
            await logger.aerror(f"Unexpected error: {e!s}")
            raise
        else:
            return result
        finally:
            # Clean up split image files after agent finishes
            # This uses the base class method
            if self._image_splitter:
                self._image_splitter.cleanup_local_files()

    def _preprocess_schema(self, schema):
        """Preprocess schema to ensure correct data types for build_model_from_schema."""
        processed_schema = []
        for field in schema:
            processed_field = {
                "name": str(field.get("name", "field")),
                "type": str(field.get("type", "str")),
                "description": str(field.get("description", "")),
                "multiple": field.get("multiple", False),
            }
            # Ensure multiple is handled correctly
            if isinstance(processed_field["multiple"], str):
                processed_field["multiple"] = processed_field["multiple"].lower() in [
                    "true",
                    "1",
                    "t",
                    "y",
                    "yes",
                ]
            processed_schema.append(processed_field)
        return processed_schema

    async def build_structured_output_base(self, content: str):
        """Build structured output with optional BaseModel validation."""
        json_pattern = r"\{.*\}"
        schema_error_msg = "Try setting an output schema"

        # Try to parse content as JSON first
        json_data = None
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(json_pattern, content, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {"content": content, "error": schema_error_msg}
            else:
                return {"content": content, "error": schema_error_msg}

        # If no output schema provided, return parsed JSON without validation
        if (
            not hasattr(self, "output_schema")
            or not self.output_schema
            or len(self.output_schema) == 0
        ):
            return json_data

        # Use BaseModel validation with schema
        try:
            processed_schema = self._preprocess_schema(self.output_schema)
            output_model = build_model_from_schema(processed_schema)

            # Validate against the schema
            if isinstance(json_data, list):
                # Multiple objects
                validated_objects = []
                for item in json_data:
                    try:
                        validated_obj = output_model.model_validate(item)
                        validated_objects.append(validated_obj.model_dump())
                    except ValidationError as e:
                        await logger.aerror(f"Validation error for item: {e}")
                        # Include invalid items with error info
                        validated_objects.append(
                            {"data": item, "validation_error": str(e)}
                        )
                return validated_objects

            # Single object
            try:
                validated_obj = output_model.model_validate(json_data)
                return [validated_obj.model_dump()]  # Return as list for consistency
            except ValidationError as e:
                await logger.aerror(f"Validation error: {e}")
                return [{"data": json_data, "validation_error": str(e)}]

        except (TypeError, ValueError) as e:
            await logger.aerror(f"Error building structured output: {e}")
            # Fallback to parsed JSON without validation
            return json_data

    async def json_response(self) -> Data:
        """Convert agent response to structured JSON Data output with schema validation."""
        # Always use structured chat agent for JSON response mode for better JSON formatting
        try:
            system_components = []

            # 1. Agent Instructions (system_prompt)
            agent_instructions = getattr(self, "system_prompt", "") or ""
            if agent_instructions:
                system_components.append(f"{agent_instructions}")

            # 2. Format Instructions
            format_instructions = getattr(self, "format_instructions", "") or ""
            if format_instructions:
                system_components.append(f"Format instructions: {format_instructions}")

            # 3. Schema Information from BaseModel
            if (
                hasattr(self, "output_schema")
                and self.output_schema
                and len(self.output_schema) > 0
            ):
                try:
                    processed_schema = self._preprocess_schema(self.output_schema)
                    output_model = build_model_from_schema(processed_schema)
                    schema_dict = output_model.model_json_schema()
                    schema_info = (
                        "You are given some text that may include format instructions, "
                        "explanations, or other content alongside a JSON schema.\n\n"
                        "Your task:\n"
                        "- Extract only the JSON schema.\n"
                        "- Return it as valid JSON.\n"
                        "- Do not include format instructions, explanations, or extra text.\n\n"
                        "Input:\n"
                        f"{json.dumps(schema_dict, indent=2)}\n\n"
                        "Output (only JSON schema):"
                    )
                    system_components.append(schema_info)
                except (ValidationError, ValueError, TypeError, KeyError) as e:
                    await logger.aerror(
                        f"Could not build schema for prompt: {e}", exc_info=True
                    )

            # Combine all components
            combined_instructions = (
                "\n\n".join(system_components) if system_components else ""
            )
            llm_model, self.chat_history, self.tools = (
                await self.get_agent_requirements()
            )
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=combined_instructions,
            )

            # Create and run structured chat agent
            try:
                structured_agent = self.create_agent_runnable()
            except (NotImplementedError, ValueError, TypeError) as e:
                await logger.aerror(f"Error with structured chat agent: {e}")
                raise
            try:
                result = await self.run_agent(structured_agent)
            except (
                ExceptionWithMessageError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as e:
                await logger.aerror(f"Error with structured agent result: {e}")
                raise
            # Extract content from structured agent result
            if hasattr(result, "content"):
                content = result.content
            elif hasattr(result, "text"):
                content = result.text
            else:
                content = str(result)

        except (
            ExceptionWithMessageError,
            ValueError,
            TypeError,
            NotImplementedError,
            AttributeError,
        ) as e:
            await logger.aerror(f"Error with structured chat agent: {e}")
            # Fallback to regular agent
            content_str = "No content returned from agent"
            return Data(data={"content": content_str, "error": str(e)})

        # Process with structured output validation
        try:
            structured_output = await self.build_structured_output_base(content)

            # Handle different output formats
            if isinstance(structured_output, list) and structured_output:
                if len(structured_output) == 1:
                    return Data(data=structured_output[0])
                return Data(data={"results": structured_output})
            if isinstance(structured_output, dict):
                return Data(data=structured_output)
            return Data(data={"content": content})

        except (ValueError, TypeError) as e:
            await logger.aerror(f"Error in structured output processing: {e}")
            return Data(data={"content": content, "error": str(e)})

    async def get_memory_data(self):
        # TODO: This is a temporary fix to avoid message duplication. We should develop a function for this.
        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(
                session_id=self.graph.session_id,
                order="Ascending",
                n_messages=self.n_messages,
            )
            .retrieve_messages()
        )
        return [
            message
            for message in messages
            if getattr(message, "id", None) != getattr(self.input_value, "id", None)
        ]

    async def get_llm(self):
        if not isinstance(self.agent_llm, str):
            return self.agent_llm, None

        try:
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if not provider_info:
                msg = f"Invalid model provider: {self.agent_llm}"
                raise ValueError(msg)

            component_class = provider_info.get("component_class")
            display_name = component_class.display_name
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix", "")

            return self._build_llm_model(component_class, inputs, prefix), display_name

        except (AttributeError, ValueError, TypeError, RuntimeError) as e:
            await logger.aerror(
                f"Error building {self.agent_llm} language model: {e!s}"
            )
            msg = f"Failed to initialize language model: {e!s}"
            raise ValueError(msg) from e

    def _build_llm_model(self, component, inputs, prefix=""):
        model_kwargs = {}
        for input_ in inputs:
            if hasattr(self, f"{prefix}{input_.name}"):
                model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")
        return component.set(**model_kwargs).build_model()

    def set_component_params(self, component):
        provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
        if provider_info:
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix")
            # Filter out json_mode and only use attributes that exist on this component
            model_kwargs = {}
            for input_ in inputs:
                if hasattr(self, f"{prefix}{input_.name}"):
                    model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")

            return component.set(**model_kwargs)
        return component

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete specified fields from build_config."""
        for field in fields:
            build_config.pop(field, None)

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config."""
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        # Existing logic for updating build_config
        if field_name in ("agent_llm",):
            build_config["agent_llm"]["value"] = field_value
            provider_info = MODEL_PROVIDERS_DICT.get(field_value)
            if provider_info:
                component_class = provider_info.get("component_class")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call the component class's update_build_config method
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )

            provider_configs: dict[str, tuple[dict, list[dict]]] = {
                provider: (
                    MODEL_PROVIDERS_DICT[provider]["fields"],
                    [
                        MODEL_PROVIDERS_DICT[other_provider]["fields"]
                        for other_provider in MODEL_PROVIDERS_DICT
                        if other_provider != provider
                    ],
                )
                for provider in MODEL_PROVIDERS_DICT
            }

            if field_value in provider_configs:
                fields_to_add, fields_to_delete = provider_configs[field_value]

                # Delete fields from other providers
                for fields in fields_to_delete:
                    self.delete_fields(build_config, fields)

                # Add provider-specific fields
                build_config.update(fields_to_add)

                # Apply provider-specific defaults (only for Azure OpenAI currently)
                if field_value == "Azure OpenAI":
                    build_config = apply_provider_defaults(field_value, build_config)

                # Reset input types for agent_llm
                build_config["agent_llm"]["input_types"] = []
                build_config["agent_llm"]["display_name"] = "Model Provider"

            elif field_value == "connect_other_models":
                # Delete all provider fields
                self.delete_fields(build_config, ALL_PROVIDER_FIELDS)
                # Update with custom component
                custom_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    info="The provider of the language model that the agent will use to generate responses.",
                    options=[*MODEL_PROVIDERS_LIST],
                    real_time_refresh=True,
                    refresh_button=False,
                    input_types=["LanguageModel"],
                    placeholder="Awaiting model input.",
                    options_metadata=[
                        MODELS_METADATA[key]
                        for key in MODEL_PROVIDERS_LIST
                        if key in MODELS_METADATA
                    ],
                    external_options={
                        "fields": {
                            "data": {
                                "node": {
                                    "name": "connect_other_models",
                                    "display_name": "Connect other models",
                                    "icon": "CornerDownLeft",
                                },
                            }
                        },
                    },
                )
                build_config.update({"agent_llm": custom_component.to_dict()})

            # Update input types for all fields
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "agent_llm",
                "tools",
                "input_value",
                "add_current_date_tool",
                "system_prompt",
                "agent_description",
                "max_iterations",
                "handle_parsing_errors",
                "verbose",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)

        # Rest of your existing method remains unchanged...
        if (
            isinstance(self.agent_llm, str)
            and self.agent_llm in MODEL_PROVIDERS_DICT
            and field_name in MODEL_DYNAMIC_UPDATE_FIELDS
        ):
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if provider_info:
                component_class = provider_info.get("component_class")
                component_class = self.set_component_params(component_class)
                prefix = provider_info.get("prefix")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call each component class's update_build_config method
                    # remove the prefix from the field_name
                    if isinstance(field_name, str) and isinstance(prefix, str):
                        field_name = field_name.replace(prefix, "")
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )
        return dotdict(
            {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in build_config.items()
            }
        )

    async def _get_tools(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"
        tools = component_toolkit(component=self).get_tools(
            tool_name="Call_Agent",
            tool_description=description,
            callbacks=self.get_langchain_callbacks(),
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(
                component=self, metadata=self.tools_metadata
            ).update_tools_metadata(tools=tools)
        return tools

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[Any]:
        return []
