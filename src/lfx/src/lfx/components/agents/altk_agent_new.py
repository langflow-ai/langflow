"""Enhanced Agent Component that combines pre-tool validation and post-tool processing capabilities."""

import ast
import json
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, cast
from altk.core.llm import get_llm
from altk.core.toolkit import AgentPhase, ComponentConfig
from altk.post_tool.code_generation.code_generation import (
    CodeGenerationComponent,
    CodeGenerationComponentConfig,
)

from altk.pre_tool.sparc import SPARCReflectionComponent
from altk.pre_tool.core import (
    SPARCExecutionMode,
    Track,
    SPARCReflectionRunInput
)
from altk.post_tool.core.toolkit import CodeGenerationRunInput
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import ChatOpenAI
from pydantic import Field

from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import data_to_messages, get_chat_output_sender_name
from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT, MODELS_METADATA
from lfx.components.agents import AgentComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.log import SendMessageFunctionType
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input."""
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
INPUT_NAMES_TO_BE_OVERRIDDEN = ["agent_llm"]


def get_parent_agent_inputs():
    return [
        input_field for input_field in AgentComponent.inputs if input_field.name not in INPUT_NAMES_TO_BE_OVERRIDDEN
    ]


# === Base Tool Wrapper Architecture ===


class BaseToolWrapper(ABC):
    """Base class for all tool wrappers in the pipeline.

    Tool wrappers can enhance tools by adding pre-execution validation,
    post-execution processing, or other capabilities.
    """

    @abstractmethod
    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Wrap a tool with enhanced functionality.

        Args:
            tool: The BaseTool to wrap
            **kwargs: Additional context for the wrapping operation

        Returns:
            A wrapped BaseTool with enhanced functionality
        """

    def initialize(self, **kwargs) -> bool:
        """Initialize any resources needed by the wrapper.

        Args:
            **kwargs: Configuration parameters for initialization

        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        return True

    @property
    def is_available(self) -> bool:
        """Check if the wrapper is available for use.

        Returns:
            bool: True if the wrapper can be used, False otherwise
        """
        return True


class ALTKBaseTool(BaseTool):
    """Base class for tools that need agent interaction and ALTK LLM access.
    
    Provides common functionality for tool execution and ALTK LLM object creation.
    """
    
    name: str = Field(...)
    description: str = Field(...)
    wrapped_tool: BaseTool = Field(...)
    agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor = Field(...)
    
    def _execute_tool(self, *args, **kwargs) -> str:
        """Execute the wrapped tool with proper error handling."""
        try:
            # Try with config parameter first (newer LangChain versions)
            if hasattr(self.wrapped_tool, "_run"):
                # Ensure config is provided for StructuredTool
                if "config" not in kwargs:
                    kwargs["config"] = {}
                return self.wrapped_tool._run(*args, **kwargs)
            return self.wrapped_tool.run(*args, **kwargs)
        except TypeError as e:
            if "config" in str(e):
                # Fallback: try without config for older tools
                kwargs.pop("config", None)
                if hasattr(self.wrapped_tool, "_run"):
                    return self.wrapped_tool._run(*args, **kwargs)
                return self.wrapped_tool.run(*args, **kwargs)
            raise e

    def _get_altk_llm_object(self, use_output_val: bool = True) -> Any:
        """Extract the LLM model and map it to altk model inputs.
        
        Args:
            use_output_val: If True, use .output_val variants for compatibility.
                           If False, use base variants (for PostToolProcessor).
        """
        llm_object: BaseChatModel | None = None
        steps = getattr(self.agent, "steps", None)
        if steps:
            for step in steps:
                if isinstance(step, RunnableBinding) and isinstance(step.bound, BaseChatModel):
                    llm_object = step.bound
                    break
        
        if isinstance(llm_object, ChatAnthropic):
            # litellm needs the prefix to the model name for anthropic
            model_name = f"anthropic/{llm_object.model}"
            api_key = llm_object.anthropic_api_key.get_secret_value()
            llm_client_type = "litellm.output_val" if use_output_val else "litellm"
            llm_client = get_llm(llm_client_type)
            llm_client_obj = llm_client(model_name=model_name, api_key=api_key)
        elif isinstance(llm_object, ChatOpenAI):
            model_name = llm_object.model_name
            api_key = llm_object.openai_api_key.get_secret_value()
            llm_client_type = "openai.sync.output_val" if use_output_val else "openai.sync"
            llm_client = get_llm(llm_client_type)
            llm_client_obj = llm_client(model=model_name, api_key=api_key)
        else:
            logger.info("ALTK currently only supports OpenAI and Anthropic models through Langflow.")
            llm_client_obj = None

        return llm_client_obj


class ValidatedTool(ALTKBaseTool):
    """A wrapper tool that validates calls before execution using SPARC reflection.
    Falls back to simple validation if SPARC is not available.
    """

    sparc_component: Any | None = Field(default=None)
    conversation_context: list[BaseMessage] = Field(default_factory=list)
    tool_specs: list[dict] = Field(default_factory=list)
    validation_attempts: dict[str, int] = Field(default_factory=dict)

    def __init__(
        self, wrapped_tool: BaseTool, agent, sparc_component=None, conversation_context=None, tool_specs=None, **kwargs
    ):
        super().__init__(
            name=wrapped_tool.name,
            description=wrapped_tool.description,
            wrapped_tool=wrapped_tool,
            sparc_component=sparc_component,
            conversation_context=conversation_context or [],
            tool_specs=tool_specs or [],
            agent=agent,
            **kwargs,
        )

    def _run(self, *args, **kwargs) -> str:
        """Execute the tool with validation."""
        self.sparc_component = SPARCReflectionComponent(
                config=ComponentConfig(llm_client=self._get_altk_llm_object()),
                track=Track.FAST_TRACK,  # Use fast track for performance
                execution_mode=SPARCExecutionMode.SYNC,  # Use SYNC to avoid event loop conflicts
            )
        return self._validate_and_run(*args, **kwargs)

    async def _arun(self, *args, **kwargs) -> str:
        """Async execute the tool with validation."""
        self.sparc_component = SPARCReflectionComponent(
                config=ComponentConfig(llm_client=self._get_altk_llm_object()),
                track=Track.FAST_TRACK,  # Use fast track for performance
                execution_mode=SPARCExecutionMode.SYNC,  # Use SYNC to avoid event loop conflicts
            )
        return self._validate_and_run(*args, **kwargs)

    def _validate_and_run(self, *args, **kwargs) -> str:
        """Validate the tool call using SPARC and execute if valid."""
        # Check if validation should be bypassed
        if not self.sparc_component:
            return self._execute_tool(*args, **kwargs)

        # Prepare tool call for SPARC validation
        tool_call = {
            "id": str(uuid.uuid4()),
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self._prepare_arguments(*args, **kwargs))},
        }

        if isinstance(self.conversation_context, list) and isinstance(self.conversation_context[0], BaseMessage):
            logger.debug("Converting BaseMessages to list of dictionaries for conversation context of SPARC")
            self.conversation_context = [dict(msg) for msg in self.conversation_context]

        try:
            # Run SPARC validation
            run_input = SPARCReflectionRunInput(
                messages=self.conversation_context, tool_specs=self.tool_specs, tool_calls=[tool_call]
            )

            # Check for missing tool specs and bypass if necessary
            if not self.tool_specs:
                logger.warning(f"No tool specs available for SPARC validation of {self.name}, executing directly")
                return self._execute_tool(*args, **kwargs)

            result = self.sparc_component.process(run_input, phase=AgentPhase.RUNTIME)

            # Check validation result
            if result.output.reflection_result.decision.name == "APPROVE":
                logger.info(f"✅ SPARC approved tool call for {self.name}")
                return self._execute_tool(*args, **kwargs)
            logger.info(f"❌ SPARC rejected tool call for {self.name}")
            error_msg = self._format_sparc_rejection(result.output.reflection_result)
            return error_msg

        except Exception as e:
            logger.error(f"Error during SPARC validation: {e}")
            # Execute directly on error
            return self._execute_tool(*args, **kwargs)

    def _prepare_arguments(self, *args, **kwargs) -> dict[str, Any]:
        """Prepare arguments for SPARC validation."""
        # Remove config parameter if present (not needed for validation)
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "config"}

        # If we have positional args, try to map them to parameter names
        if args and hasattr(self.wrapped_tool, "args_schema"):
            try:
                schema = self.wrapped_tool.args_schema
                if hasattr(schema, "__fields__"):
                    field_names = list(schema.__fields__.keys())
                    for i, arg in enumerate(args):
                        if i < len(field_names):
                            clean_kwargs[field_names[i]] = arg
            except Exception:
                # If schema parsing fails, just use kwargs
                pass

        return clean_kwargs

    def _format_sparc_rejection(self, reflection_result) -> str:
        """Format SPARC rejection into a helpful error message."""
        if not reflection_result.issues:
            return "Error: Tool call validation failed - please review your approach and try again"

        error_parts = ["Tool call validation failed:"]

        for issue in reflection_result.issues:
            error_parts.append(f"\n• {issue.explanation}")
            if issue.correction:
                try:
                    correction_data = issue.correction
                    if isinstance(correction_data, dict):
                        if "corrected_function_name" in correction_data:
                            error_parts.append(f"  💡 Suggested function: {correction_data['corrected_function_name']}")
                        elif "tool_call" in correction_data:
                            suggested_args = correction_data["tool_call"].get("arguments", {})
                            error_parts.append(f"  💡 Suggested parameters: {suggested_args}")
                except Exception:
                    # If correction parsing fails, skip it
                    pass

        error_parts.append("\nPlease adjust your approach and try again.")
        return "\n".join(error_parts)

    def update_context(self, conversation_context: list[BaseMessage]):
        """Update the conversation context."""
        self.conversation_context = conversation_context


class PreToolValidationWrapper(BaseToolWrapper):
    """Tool wrapper that adds pre-tool validation capabilities.

    This wrapper validates tool calls before execution using the SPARC
    reflection component to check for appropriateness and correctness.
    """

    def __init__(self):
        self.tool_specs = []

    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Wrap a tool with validation functionality.

        Args:
            tool: The BaseTool to wrap
            **kwargs: May contain 'conversation_context' for improved validation

        Returns:
            A wrapped BaseTool with validation capabilities
        """
        if isinstance(tool, ValidatedTool):
            # Already wrapped, update context and tool specs
            tool.tool_specs = self.tool_specs
            if "conversation_context" in kwargs:
                tool.update_context(kwargs["conversation_context"])
            logger.debug(f"Updated existing ValidatedTool {tool.name} with {len(self.tool_specs)} tool specs")
            return tool
        
        agent = kwargs.get("agent")
        
        if not agent:
            logger.warning("Cannot wrap tool with PostToolProcessor: missing 'agent'")
            return tool


        # Wrap with validation
        validated_tool = ValidatedTool(
            wrapped_tool=tool,
            agent=agent,
            tool_specs=self.tool_specs,
            conversation_context=kwargs.get("conversation_context", []),
        )

        return validated_tool

    @staticmethod
    def convert_langchain_tools_to_sparc_tool_specs_format(tools: list[BaseTool]) -> list[dict]:
        """Convert LangChain tools to SPARC tool specifications."""
        tool_specs = []

        for i, tool in enumerate(tools):
            try:
                # Handle nested wrappers
                unwrapped_tool = tool
                wrapper_count = 0

                # Unwrap to get to the actual tool
                while hasattr(unwrapped_tool, "wrapped_tool") and not isinstance(unwrapped_tool, ValidatedTool):
                    unwrapped_tool = unwrapped_tool.wrapped_tool
                    wrapper_count += 1
                    if wrapper_count > 10:  # Prevent infinite loops
                        break

                # Build tool spec from LangChain tool
                tool_spec = {
                    "type": "function",
                    "function": {
                        "name": unwrapped_tool.name,
                        "description": unwrapped_tool.description or f"Tool: {unwrapped_tool.name}",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }

                # Extract parameters from tool schema if available
                if hasattr(unwrapped_tool, "args_schema") and unwrapped_tool.args_schema:
                    schema = unwrapped_tool.args_schema
                    if hasattr(schema, "__fields__"):
                        for field_name, field_info in schema.__fields__.items():
                            param_spec = {
                                "type": "string",  # Default type
                                "description": getattr(field_info, "description", f"Parameter {field_name}"),
                            }

                            # Try to infer type from field info
                            if hasattr(field_info, "type_"):
                                if field_info.type_ == int:
                                    param_spec["type"] = "integer"
                                elif field_info.type_ == float:
                                    param_spec["type"] = "number"
                                elif field_info.type_ == bool:
                                    param_spec["type"] = "boolean"

                            tool_spec["function"]["parameters"]["properties"][field_name] = param_spec

                            # Check if field is required
                            if hasattr(field_info, "is_required") and field_info.is_required():
                                tool_spec["function"]["parameters"]["required"].append(field_name)

                tool_specs.append(tool_spec)

            except Exception as e:
                logger.warning(f"Could not convert tool {getattr(tool, 'name', 'unknown')} to spec: {e}")
                # Create minimal spec
                minimal_spec = {
                    "type": "function",
                    "function": {
                        "name": getattr(tool, "name", f"unknown_tool_{i}"),
                        "description": getattr(tool, "description", f"Tool: {getattr(tool, 'name', 'unknown')}"),
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
                tool_specs.append(minimal_spec)

        if not tool_specs:
            logger.error("⚠️ No tool specs were generated! This will cause SPARC validation to fail")
        return tool_specs


class ToolPipelineManager:
    """Manages the tool wrapping pipeline.

    The pipeline can contain multiple wrappers that are applied
    in sequence to transform or enhance tools. The wrappers are
    applied in reverse order so the first wrapper is the outermost
    wrapper and the last wrapper is the innermost wrapper.
    """

    def __init__(self):
        self.wrappers: list[BaseToolWrapper] = []

    def add_wrapper(self, wrapper: BaseToolWrapper):
        """Add a wrapper to the pipeline.

        Args:
            wrapper: A BaseToolWrapper implementation to add to the pipeline
        """
        self.wrappers.append(wrapper)

    def process_tools(self, tools: list[BaseTool], **kwargs) -> list[BaseTool]:
        """Apply all wrappers to the tools in reverse order of registration."""
        # Update tool specs for validation wrappers
        self._update_validation_tool_specs(tools)

        # Apply wrappers to each tool
        return [self._apply_wrappers_to_tool(tool, **kwargs) for tool in tools]

    def _update_validation_tool_specs(self, tools: list[BaseTool]) -> None:
        """Update tool specs for validation wrappers with the actual tools."""
        for wrapper in self.wrappers:
            if isinstance(wrapper, PreToolValidationWrapper) and tools:
                wrapper.tool_specs = wrapper.convert_langchain_tools_to_sparc_tool_specs_format(tools)
                logger.info(f"Updated tool specs for validation: {len(wrapper.tool_specs)} tools")

    def _apply_wrappers_to_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Apply all available wrappers to a tool in reverse order."""
        wrapped_tool = tool

        for wrapper in reversed(self.wrappers):
            if wrapper.is_available:
                wrapped_tool = wrapper.wrap_tool(wrapped_tool, **kwargs)
        return wrapped_tool


# === Post Tool Processing Implementation ===


class PostToolProcessor(ALTKBaseTool):
    """A tool output processor to process tool outputs.

    This wrapper intercepts the tool execution output and
    if the tool output is a JSON, it invokes an ALTK component
    to extract information from the JSON by generating Python code.
    """

    user_query: str = Field(...)
    response_processing_size_threshold: int = Field(...)

    def __init__(
        self, wrapped_tool: BaseTool, user_query: str, agent, response_processing_size_threshold: int, **kwargs
    ):
        super().__init__(
            name=wrapped_tool.name,
            description=wrapped_tool.description,
            wrapped_tool=wrapped_tool,
            user_query=user_query,
            agent=agent,
            response_processing_size_threshold=response_processing_size_threshold,
            **kwargs,
        )

    def _run(self, *args: Any, **kwargs: Any) -> str:
        # Run the wrapped tool
        result = self._execute_tool(*args, **kwargs)

        try:
            # Run postprocessing and return the output
            return self.process_tool_response(result)
        except Exception as e:
            # If post-processing fails, log the error and return the original result
            logger.error(f"Error in post-processing tool response: {e}")
            return result

    # async def _arun(self, *args: Any, **kwargs: Any) -> str:
    #     # Run the wrapped tool synchronously for now (can be enhanced for async later)
    #     return self._run(*args, **kwargs)

    def _get_tool_response_str(self, tool_response) -> str:
        """Convert various tool response formats to a string representation."""
        if isinstance(tool_response, str):
            tool_response_str = tool_response
        elif isinstance(tool_response, Data):
            tool_response_str = str(tool_response.data)
        elif isinstance(tool_response, list) and all(isinstance(item, Data) for item in tool_response):
            # get only the first element, not 100% sure if it should be the first or the last
            tool_response_str = str(tool_response[0].data)
        elif isinstance(tool_response, (dict, list)):
            tool_response_str = str(tool_response)
        else:
            # Return empty string instead of None to avoid type errors
            tool_response_str = str(tool_response) if tool_response is not None else ""

        return tool_response_str

    def process_tool_response(self, tool_response: str, **_kwargs) -> str:
        logger.info("Calling process_tool_response of PostToolProcessor")
        tool_response_str = self._get_tool_response_str(tool_response)

        # First check if this looks like an error message with bullet points (SPARC rejection)
        if "❌" in tool_response_str or "•" in tool_response_str:
            logger.info("Detected error message with special characters, skipping JSON parsing")
            return tool_response_str

        try:
            # Only attempt to parse content that looks like JSON
            if (tool_response_str.startswith("{") and tool_response_str.endswith("}")) or (
                tool_response_str.startswith("[") and tool_response_str.endswith("]")
            ):
                tool_response_json = ast.literal_eval(tool_response_str)
                if not isinstance(tool_response_json, (list, dict)):
                    tool_response_json = None
            else:
                tool_response_json = None
        except (json.JSONDecodeError, TypeError, SyntaxError, ValueError) as e:
            logger.info(
                f"An error in converting the tool response to json, this will skip the code generation component: {e}"
            )
            tool_response_json = None

        if tool_response_json is not None and len(str(tool_response_json)) > self.response_processing_size_threshold:
            llm_client_obj = self._get_altk_llm_object(use_output_val=False)
            if llm_client_obj is not None:
                config = CodeGenerationComponentConfig(llm_client=llm_client_obj, use_docker_sandbox=False)

                middleware = CodeGenerationComponent(config=config)
                input_data = CodeGenerationRunInput(
                    messages=[], nl_query=self.user_query, tool_response=tool_response_json
                )
                output = None
                try:
                    output = middleware.process(input_data, AgentPhase.RUNTIME)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Exception in executing CodeGenerationComponent: {e}")
                logger.info(f"Output of CodeGenerationComponent: {output.result}")
                return output.result
        return tool_response


class PostToolProcessingWrapper(BaseToolWrapper):
    """Tool wrapper that adds post-tool processing capabilities.

    This wrapper processes the output of tool calls, particularly JSON responses,
    using the ALTK code generation component to extract useful information.
    """

    def __init__(self, response_processing_size_threshold: int = 100):
        self.response_processing_size_threshold = response_processing_size_threshold

    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Wrap a tool with post-processing functionality.

        Args:
            tool: The BaseTool to wrap
            **kwargs: Must contain 'agent' and 'user_query'

        Returns:
            A wrapped BaseTool with post-processing capabilities
        """
        logger.info(f"Post-tool reflection enabled for {tool.name}")
        if isinstance(tool, PostToolProcessor):
            # Already wrapped with this wrapper, just return it
            return tool

        # Required kwargs
        agent = kwargs.get("agent")
        user_query = kwargs.get("user_query", "")

        if not agent:
            logger.warning("Cannot wrap tool with PostToolProcessor: missing 'agent'")
            return tool

        # If the tool is already wrapped by another wrapper, we need to get the innermost tool
        actual_tool = tool

        return PostToolProcessor(
            wrapped_tool=actual_tool,
            user_query=user_query,
            agent=agent,
            response_processing_size_threshold=self.response_processing_size_threshold,
        )


# === Combined Enhanced Agent Component ===


class EnhancedAgentComponent(AgentComponent):
    """Enhanced Agent with both pre-tool validation and post-tool processing capabilities.

    This agent combines the functionality of both ALTKAgent and AgentReflection components,
    implementing a modular pipeline for tool processing that can be extended with
    additional capabilities in the future.
    """

    display_name: str = "ALTK Enhanced Agent"
    description: str = "Advanced agent with both pre-tool validation and post-tool processing capabilities."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "zap"
    beta = True
    name = "ALTK Enhanced Agent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

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
            options_metadata=[MODELS_METADATA[key] for key in MODEL_PROVIDERS_LIST if key in MODELS_METADATA],
        ),
        *get_parent_agent_inputs(),
        BoolInput(
            name="enable_tool_validation",
            display_name="Tool Validation",
            info="Validates tool calls using SPARC before execution.",
            value=True,
        ),
        BoolInput(
            name="enable_post_tool_reflection",
            display_name="Post Tool JSON Processing",
            info="Processes tool output through JSON analysis.",
            value=True,
        ),
        IntInput(
            name="response_processing_size_threshold",
            display_name="Response Processing Size Threshold",
            value=100,
            info="Tool output is post-processed only if response exceeds this character threshold.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    def __init__(self, **kwargs):
        # Default values for configuration flags
        super().__init__(**kwargs)
        self.pipeline_manager = ToolPipelineManager()

    def _initialize_tool_wrappers(self):
        """Initialize tool wrappers based on enabled features."""
        # Add post-tool processing first (innermost wrapper)
        if self.enable_post_tool_reflection:
            logger.info("Enabling Post-Tool Processing Wrapper!")
            post_processor = PostToolProcessingWrapper(
                response_processing_size_threshold=self.response_processing_size_threshold
            )
            self.pipeline_manager.add_wrapper(post_processor)

        # Add pre-tool validation last (outermost wrapper)
        if self.enable_tool_validation:
            logger.info("Enabling Pre-Tool Validation Wrapper!")
            pre_validator = PreToolValidationWrapper()
            self.pipeline_manager.add_wrapper(pre_validator)

    def update_runnable_instance(
        self, agent: AgentExecutor, runnable: AgentExecutor, tools: Sequence[BaseTool]
    ) -> AgentExecutor:
        user_query = self.input_value.get_text() if hasattr(self.input_value, "get_text") else self.input_value

        # Prepare conversation context for tool validation
        conversation_context = []
        if hasattr(self, "input_value") and self.input_value:
            if isinstance(self.input_value, Message):
                conversation_context.append(self.input_value.to_lc_message())
            else:
                conversation_context.append(HumanMessage(content=str(self.input_value)))

        if hasattr(self, "chat_history") and self.chat_history:
            if isinstance(self.chat_history, Data):
                conversation_context.extend(data_to_messages(self.chat_history))
            elif all(isinstance(m, Message) for m in self.chat_history):
                conversation_context.extend([m.to_lc_message() for m in self.chat_history])

        self._initialize_tool_wrappers()

        # Process tools through the pipeline
        processed_tools = self.pipeline_manager.process_tools(
            tools or [],
            agent=agent,
            user_query=user_query,
            conversation_context=conversation_context,
        )

        runnable.tools = processed_tools

        return runnable

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            # note the tools are not required to run the agent, hence the validation removed.
            handle_parsing_errors = hasattr(self, "handle_parsing_errors") and self.handle_parsing_errors
            verbose = hasattr(self, "verbose") and self.verbose
            max_iterations = hasattr(self, "max_iterations") and self.max_iterations
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools or [],
                handle_parsing_errors=handle_parsing_errors,
                verbose=verbose,
                max_iterations=max_iterations,
            )
        runnable = self.update_runnable_instance(agent, runnable, self.tools)

        # Convert input_value to proper format for agent
        if hasattr(self.input_value, "to_lc_message") and callable(self.input_value.to_lc_message):
            lc_message = self.input_value.to_lc_message()
            input_text = lc_message.content if hasattr(lc_message, "content") else str(lc_message)
        else:
            lc_message = None
            input_text = self.input_value

        input_dict: dict[str, str | list[BaseMessage]] = {}
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
        if hasattr(self, "chat_history") and self.chat_history:
            if (
                hasattr(self.chat_history, "to_data")
                and callable(self.chat_history.to_data)
                and self.chat_history.__class__.__name__ == "Data"
            ):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            # Handle both lfx.schema.message.Message and langflow.schema.message.Message types
            if all(hasattr(m, "to_data") and callable(m.to_data) and "text" in m.data for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            if all(isinstance(m, Message) for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages([m.to_data() for m in self.chat_history])
        if hasattr(lc_message, "content") and isinstance(lc_message.content, list):
            # ! Because the input has to be a string, we must pass the images in the chat_history

            image_dicts = [item for item in lc_message.content if item.get("type") == "image"]
            lc_message.content = [item for item in lc_message.content if item.get("type") != "image"]

            if "chat_history" not in input_dict:
                input_dict["chat_history"] = []
            if isinstance(input_dict["chat_history"], list):
                input_dict["chat_history"].extend(HumanMessage(content=[image_dict]) for image_dict in image_dicts)
            else:
                input_dict["chat_history"] = [HumanMessage(content=[image_dict]) for image_dict in image_dicts]
        input_dict["input"] = input_text
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        try:
            sender_name = get_chat_output_sender_name(self)
        except AttributeError:
            sender_name = self.display_name or "AI"

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )
        try:
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                    version="v2",
                ),
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
            )
        except ExceptionWithMessageError as e:
            if hasattr(e, "agent_message") and hasattr(e.agent_message, "id"):
                msg_id = e.agent_message.id
                await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            logger.error(f"ExceptionWithMessageError: {e}")
            raise
        except Exception as e:
            # Log or handle any other exceptions
            logger.error(f"Error: {e}")
            raise

        self.status = result
        return result
