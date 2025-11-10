import ast
import json
import uuid
from altk.core.toolkit import AgentPhase, ComponentConfig
from altk.post_tool.code_generation.code_generation import CodeGenerationComponent, CodeGenerationComponentConfig
from altk.post_tool.core.toolkit import CodeGenerationRunInput
from typing import Any
from altk.pre_tool.core import SPARCExecutionMode, SPARCReflectionRunInput, Track
from altk.pre_tool.sparc import SPARCReflectionComponent
from langchain_core.messages import BaseMessage
from langchain_core.messages.base import message_to_dict
from langchain_core.tools import BaseTool
from lfx.components.agents.altk_base_agent import ALTKBaseTool, BaseToolWrapper
from lfx.log.logger import logger
from lfx.schema.data import Data
from pydantic import Field


class ValidatedTool(ALTKBaseTool):
    """A wrapper tool that validates calls before execution using SPARC reflection.
    Falls back to simple validation if SPARC is not available.
    """

    sparc_component: Any | None = Field(default=None)
    conversation_context: list[BaseMessage] = Field(default_factory=list)
    tool_specs: list[dict] = Field(default_factory=list)
    validation_attempts: dict[str, int] = Field(default_factory=dict)
    current_conversation_context: list[BaseMessage] = Field(default_factory=list)
    previous_tool_calls_in_current_step: list[dict] = Field(default_factory=list)
    previous_reflection_messages: dict[str, str] = Field(default_factory=list)

    def __init__(
        self,
        wrapped_tool: BaseTool,
        agent,
        sparc_component=None,
        conversation_context=None,
        tool_specs=None,
        **kwargs,
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


    def _validate_and_run(self, *args, **kwargs) -> str:
        """Validate the tool call using SPARC and execute if valid."""
        # Check if validation should be bypassed
        if not self.sparc_component:
            return self._execute_tool(*args, **kwargs)

        # Prepare tool call for SPARC validation
        tool_call = {
            "id": str(uuid.uuid4()),
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self._prepare_arguments(*args, **kwargs)),
            },
        }

        if (
            isinstance(self.conversation_context, list)
            and self.conversation_context
            and isinstance(self.conversation_context[0], BaseMessage)
        ):
            logger.debug(
                "Converting BaseMessages to list of dictionaries for conversation context of SPARC"
            )
            self.conversation_context = [
                message_to_dict(msg) for msg in self.conversation_context
            ]

        logger.debug(f"Converted conversation context for SPARC for tool call:\n{json.dumps(tool_call, indent=2)}\n{self.conversation_context=}")

        try:
            # Run SPARC validation
            run_input = SPARCReflectionRunInput(
                messages=self.conversation_context + self.previous_tool_calls_in_current_step,
                tool_specs=self.tool_specs,
                tool_calls=[tool_call],
            )

            if self.current_conversation_context != self.conversation_context:
                logger.info("Updating conversation context for SPARC validation")
                self.current_conversation_context = self.conversation_context
                self.previous_tool_calls_in_current_step = []
            else:
                logger.info("Using existing conversation context for SPARC validation")
                self.previous_tool_calls_in_current_step.append(tool_call)

            # Check for missing tool specs and bypass if necessary
            if not self.tool_specs:
                logger.warning(
                    f"No tool specs available for SPARC validation of {self.name}, executing directly"
                )
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
                            error_parts.append(
                                f"  💡 Suggested function: {correction_data['corrected_function_name']}"
                            )
                        elif "tool_call" in correction_data:
                            suggested_args = correction_data["tool_call"].get(
                                "arguments", {}
                            )
                            error_parts.append(
                                f"  💡 Suggested parameters: {suggested_args}"
                            )
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
            logger.debug(
                f"Updated existing ValidatedTool {tool.name} with {len(self.tool_specs)} tool specs"
            )
            return tool

        agent = kwargs.get("agent")

        if not agent:
            logger.warning("Cannot wrap tool with PreToolValidationWrapper: missing 'agent'")
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
    def convert_langchain_tools_to_sparc_tool_specs_format(
        tools: list[BaseTool],
    ) -> list[dict]:
        """Convert LangChain tools to SPARC tool specifications."""
        tool_specs = []

        for i, tool in enumerate(tools):
            try:
                # Handle nested wrappers
                unwrapped_tool = tool
                wrapper_count = 0

                # Unwrap to get to the actual tool
                while hasattr(unwrapped_tool, "wrapped_tool") and not isinstance(
                    unwrapped_tool, ValidatedTool
                ):
                    unwrapped_tool = unwrapped_tool.wrapped_tool
                    wrapper_count += 1
                    if wrapper_count > 10:  # Prevent infinite loops
                        break

                # Build tool spec from LangChain tool
                tool_spec = {
                    "type": "function",
                    "function": {
                        "name": unwrapped_tool.name,
                        "description": unwrapped_tool.description
                        or f"Tool: {unwrapped_tool.name}",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }

                # Extract parameters from tool schema if available
                args_dict = unwrapped_tool.args
                if isinstance(args_dict, dict):
                    for param_name, param_info in args_dict.items():
                        logger.debug("Field name:", param_name)
                        logger.debug("Field info:", param_info)
                        param_spec = {
                            "type": param_info.get("type", "string"),
                            "description": param_info.get("description", ""),
                        }

                        if unwrapped_tool.args_schema and hasattr(
                            unwrapped_tool.args_schema, "model_fields"
                        ):
                            field_info = unwrapped_tool.args_schema.model_fields.get(
                                param_name
                            )
                            if field_info.is_required():
                                tool_spec["function"]["parameters"]["required"].append(
                                    param_name
                                )
                        tool_spec["function"]["parameters"]["properties"][
                            param_name
                        ] = param_spec

                tool_specs.append(tool_spec)

            except Exception as e:
                logger.warning(
                    f"Could not convert tool {getattr(tool, 'name', 'unknown')} to spec: {e}"
                )
                # Create minimal spec
                minimal_spec = {
                    "type": "function",
                    "function": {
                        "name": getattr(tool, "name", f"unknown_tool_{i}"),
                        "description": getattr(
                            tool,
                            "description",
                            f"Tool: {getattr(tool, 'name', 'unknown')}",
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }
                tool_specs.append(minimal_spec)

        if not tool_specs:
            logger.error(
                "⚠️ No tool specs were generated! This will cause SPARC validation to fail"
            )
        return tool_specs


class PostToolProcessor(ALTKBaseTool):
    """A tool output processor to process tool outputs.

    This wrapper intercepts the tool execution output and
    if the tool output is a JSON, it invokes an ALTK component
    to extract information from the JSON by generating Python code.
    """

    user_query: str = Field(...)
    response_processing_size_threshold: int = Field(...)

    def __init__(
        self,
        wrapped_tool: BaseTool,
        user_query: str,
        agent,
        response_processing_size_threshold: int,
        **kwargs,
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

    def _get_tool_response_str(self, tool_response) -> str:
        """Convert various tool response formats to a string representation."""
        if isinstance(tool_response, str):
            tool_response_str = tool_response
        elif isinstance(tool_response, Data):
            tool_response_str = str(tool_response.data)
        elif isinstance(tool_response, list) and all(
            isinstance(item, Data) for item in tool_response
        ):
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
            logger.info(
                "Detected error message with special characters, skipping JSON parsing"
            )
            return tool_response_str

        try:
            # Only attempt to parse content that looks like JSON
            if (
                tool_response_str.startswith("{") and tool_response_str.endswith("}")
            ) or (
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

        if (
            tool_response_json is not None
            and len(str(tool_response_json)) > self.response_processing_size_threshold
        ):
            llm_client_obj = self._get_altk_llm_object(use_output_val=False)
            if llm_client_obj is not None:
                config = CodeGenerationComponentConfig(
                    llm_client=llm_client_obj, use_docker_sandbox=False
                )

                middleware = CodeGenerationComponent(config=config)
                input_data = CodeGenerationRunInput(
                    messages=[],
                    nl_query=self.user_query,
                    tool_response=tool_response_json,
                )
                output = None
                try:
                    output = middleware.process(input_data, AgentPhase.RUNTIME)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Exception in executing CodeGenerationComponent: {e}")
                if output is not None and hasattr(output, "result"):
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