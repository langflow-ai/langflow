"""
Enhanced Agent Component that combines pre-tool validation and post-tool processing capabilities.
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

import ast
from altk.post_tool_reflection_toolkit.code_generation.code_generation import (
    CodeGenerationComponent,
    CodeGenerationComponentConfig,
)
from altk.post_tool_reflection_toolkit.core.toolkit import CodeGenerationRunInput
from altk.toolkit_core.core.toolkit import AgentPhase, ComponentConfig
from altk.toolkit_core.llm import get_llm
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.callbacks.base import BaseCallbackHandler
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import ChatOpenAI
from pydantic import Field

from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import data_to_messages
from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT
from lfx.components.agents import AgentComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import IntInput, Output
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from lfx.schema.log import SendMessageFunctionType

def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input."""
    component_input.advanced = True
    return component_input

# SPARC imports - use lazy loading to avoid module caching issues
SPARCReflectionRunInput = None
SPARCExecutionMode = None
Track = None
SPARCReflectionComponent = None


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
        pass
        
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


class ValidatedTool(BaseTool):
    """
    A wrapper tool that validates calls before execution using SPARC reflection.
    Falls back to simple validation if SPARC is not available.
    """
    
    name: str = Field(...)
    description: str = Field(...)
    wrapped_tool: BaseTool = Field(...)
    sparc_component: Optional[Any] = Field(default=None)
    conversation_context: List[BaseMessage] = Field(default_factory=list)
    tool_specs: List[Dict] = Field(default_factory=list)
    validation_attempts: Dict[str, int] = Field(default_factory=dict)
    
    def __init__(self, wrapped_tool: BaseTool, sparc_component=None, conversation_context=None, tool_specs=None, **kwargs):
        super().__init__(
            name=wrapped_tool.name,
            description=wrapped_tool.description,
            wrapped_tool=wrapped_tool,
            sparc_component=sparc_component,
            conversation_context=conversation_context or [],
            tool_specs=tool_specs or [],
            **kwargs
        )
    
    def _run(self, *args, **kwargs) -> str:
        """Execute the tool with validation."""
        return self._validate_and_run(*args, **kwargs)
    
    async def _arun(self, *args, **kwargs) -> str:
        """Async execute the tool with validation."""
        return self._validate_and_run(*args, **kwargs)
    
    def _validate_and_run(self, *args, **kwargs) -> str:
        """Validate the tool call using SPARC and execute if valid."""
        # Check if validation should be bypassed
        if not _check_sparc_available() or not self.sparc_component or kwargs.get("bypass_validation", False):
            if kwargs.get("bypass_validation", False):
                kwargs.pop("bypass_validation", None)
            return self._execute_tool(*args, **kwargs)
        
        # Prepare tool call for SPARC validation
        tool_call = {
            "id": str(uuid.uuid4()),
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self._prepare_arguments(*args, **kwargs))
            }
        }
        
        try:
            # Run SPARC validation
            run_input = SPARCReflectionRunInput(
                messages=self.conversation_context,
                tool_specs=self.tool_specs,
                tool_calls=[tool_call]
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
            else:
                logger.info(f"❌ SPARC rejected tool call for {self.name}")
                error_msg = self._format_sparc_rejection(result.output.reflection_result)
                return error_msg
                
        except Exception as e:
            logger.error(f"Error during SPARC validation: {e}")
            # Execute directly on error
            return self._execute_tool(*args, **kwargs)
    
    def _prepare_arguments(self, *args, **kwargs) -> Dict[str, Any]:
        """Prepare arguments for SPARC validation."""
        # Remove config parameter if present (not needed for validation)
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'config'}
        
        # If we have positional args, try to map them to parameter names
        if args and hasattr(self.wrapped_tool, 'args_schema'):
            try:
                schema = self.wrapped_tool.args_schema
                if hasattr(schema, '__fields__'):
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
                        if 'corrected_function_name' in correction_data:
                            error_parts.append(f"  💡 Suggested function: {correction_data['corrected_function_name']}")
                        elif 'tool_call' in correction_data:
                            suggested_args = correction_data['tool_call'].get('arguments', {})
                            error_parts.append(f"  💡 Suggested parameters: {suggested_args}")
                except Exception:
                    # If correction parsing fails, skip it
                    pass
        
        error_parts.append("\nPlease adjust your approach and try again.")
        return "\n".join(error_parts)
    
    def _execute_tool(self, *args, **kwargs) -> str:
        """Execute the wrapped tool with proper error handling."""
        try:
            # Try with config parameter first (newer LangChain versions)
            if hasattr(self.wrapped_tool, '_run'):
                # Ensure config is provided for StructuredTool
                if 'config' not in kwargs:
                    kwargs['config'] = {}
                return self.wrapped_tool._run(*args, **kwargs)
            else:
                return self.wrapped_tool.run(*args, **kwargs)
        except TypeError as e:
            if "config" in str(e):
                # Fallback: try without config for older tools
                kwargs.pop('config', None)
                if hasattr(self.wrapped_tool, '_run'):
                    return self.wrapped_tool._run(*args, **kwargs)
                else:
                    return self.wrapped_tool.run(*args, **kwargs)
            else:
                raise e
    
    def update_context(self, conversation_context: List[BaseMessage]):
        """Update the conversation context."""
        self.conversation_context = conversation_context


class PreToolValidationWrapper(BaseToolWrapper):
    """Tool wrapper that adds pre-tool validation capabilities.
    
    This wrapper validates tool calls before execution using the SPARC
    reflection component to check for appropriateness and correctness.
    """
    
    def __init__(self):
        self.sparc_component = None
        self.tool_specs = []
        self.available = self._initialize_sparc_component()
        
    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Wrap a tool with validation functionality.
        
        Args:
            tool: The BaseTool to wrap
            **kwargs: May contain 'conversation_context' for improved validation
                      and 'enable_validation' to determine if validation should be applied
            
        Returns:
            A wrapped BaseTool with validation capabilities
        """
        # Check if validation is explicitly disabled
        enable_validation = kwargs.get("enable_validation", True)
        if not enable_validation:
            logger.info(f"Tool validation explicitly disabled for {tool.name}")
            return tool
            
        if isinstance(tool, ValidatedTool):
            # Already wrapped, update context and tool specs
            tool.sparc_component = self.sparc_component
            tool.tool_specs = self.tool_specs
            if "conversation_context" in kwargs:
                tool.update_context(kwargs["conversation_context"])
            logger.debug(f"Updated existing ValidatedTool {tool.name} with {len(self.tool_specs)} tool specs")
            return tool
            
        # Wrap with validation
        validated_tool = ValidatedTool(
            wrapped_tool=tool,
            sparc_component=self.sparc_component,
            tool_specs=self.tool_specs,
            conversation_context=kwargs.get("conversation_context", [])
        )
        
        if self.sparc_component:
            logger.info(f"Wrapped tool '{tool.name}' with SPARC validation ({len(self.tool_specs)} tool specs)")
        else:
            logger.info(f"Wrapped tool '{tool.name}' with fallback validation")
            
        return validated_tool
        
    @property
    def is_available(self) -> bool:
        """Check if the SPARC component is available."""
        return self.available
        
    def _initialize_sparc_component(self) -> bool:
        """Initialize the SPARC reflection component if available."""
        # Use lazy loading to check SPARC availability
        if not _check_sparc_available():
            logger.warning("SPARC toolkit not available - tool validation will be disabled")
            return False
        
        try:
            # Load .env file explicitly to ensure variables are available
            from dotenv import load_dotenv
            from pathlib import Path
            
            # Try to load .env from project root
            env_path = Path(__file__).parents[6] / '.env'  # Navigate up to project root
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"Loaded .env from {env_path}")
            else:
                load_dotenv()  # Try default locations
                logger.debug("Loaded .env from default location")
            
            logger.info("Initializing SPARC reflection component...")
            
            # Check if required environment variables are available
            api_key = os.getenv("WX_API_KEY")
            project_id = os.getenv("WX_PROJECT_ID")
            url = os.getenv("WX_URL", "https://us-south.ml.cloud.ibm.com")
            
            if not api_key or not project_id:
                logger.warning("WatsonX credentials not found in environment - SPARC validation will be disabled")
                logger.info("Set WX_API_KEY and WX_PROJECT_ID environment variables to enable SPARC")
                return False
            
            logger.info(f"Using WatsonX URL: {url}")
            logger.info(f"Using project ID: {project_id[:8]}...")
            
            # Build ComponentConfig with WatsonX ValidatingLLMClient
            WATSONX_CLIENT = get_llm("watsonx.output_val")
            
            config = ComponentConfig(
                llm_client=WATSONX_CLIENT(
                    model_id="meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
                    api_key=api_key,
                    project_id=project_id,
                    url=url,
                )
            )
            
            self.sparc_component = SPARCReflectionComponent(
                config=config,
                track=Track.FAST_TRACK,  # Use fast track for performance
                execution_mode=SPARCExecutionMode.SYNC,  # Use SYNC to avoid event loop conflicts
            )
            
            if hasattr(self.sparc_component, '_initialization_error') and self.sparc_component._initialization_error:
                logger.error(f"SPARC component has initialization error: {self.sparc_component._initialization_error}")
                return False
            else:
                logger.info("✅ SPARC reflection component initialized successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error initializing SPARC component: {e}")
            logger.exception("Full traceback:")
            return False
    
    @staticmethod
    def convert_langchain_tools_to_sparc_tool_specs_format(tools: List[BaseTool]) -> List[Dict]:
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
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
                
                # Extract parameters from tool schema if available
                if hasattr(unwrapped_tool, 'args_schema') and unwrapped_tool.args_schema:
                    schema = unwrapped_tool.args_schema
                    if hasattr(schema, '__fields__'):
                        for field_name, field_info in schema.__fields__.items():
                            param_spec = {
                                "type": "string",  # Default type
                                "description": getattr(field_info, 'description', f"Parameter {field_name}")
                            }
                            
                            # Try to infer type from field info
                            if hasattr(field_info, 'type_'):
                                if field_info.type_ == int:
                                    param_spec["type"] = "integer"
                                elif field_info.type_ == float:
                                    param_spec["type"] = "number"
                                elif field_info.type_ == bool:
                                    param_spec["type"] = "boolean"
                            
                            tool_spec["function"]["parameters"]["properties"][field_name] = param_spec
                            
                            # Check if field is required
                            if hasattr(field_info, 'is_required') and field_info.is_required():
                                tool_spec["function"]["parameters"]["required"].append(field_name)
                
                tool_specs.append(tool_spec)
                
            except Exception as e:
                logger.warning(f"Could not convert tool {getattr(tool, 'name', 'unknown')} to spec: {e}")
                # Create minimal spec
                minimal_spec = {
                    "type": "function",
                    "function": {
                        "name": getattr(tool, 'name', f'unknown_tool_{i}'),
                        "description": getattr(tool, 'description', f"Tool: {getattr(tool, 'name', 'unknown')}"),
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
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
        self.wrappers: List[BaseToolWrapper] = []
        
    @property
    def has_wrappers(self) -> bool:
        """Check if any wrappers are registered.
        
        Returns:
            bool: True if wrappers are available, False otherwise
        """
        return len(self.wrappers) > 0
        
    def add_wrapper(self, wrapper: BaseToolWrapper):
        """Add a wrapper to the pipeline.
        
        Args:
            wrapper: A BaseToolWrapper implementation to add to the pipeline
        """
        self.wrappers.append(wrapper)
        
    def process_tools(self, tools: List[BaseTool], **kwargs) -> List[BaseTool]:
        """Apply all wrappers to the tools in reverse order of registration."""
        # Update tool specs for validation wrappers
        self._update_validation_tool_specs(tools)
        
        # Apply wrappers to each tool
        return [self._apply_wrappers_to_tool(tool, **kwargs) for tool in tools]
    
    def _update_validation_tool_specs(self, tools: List[BaseTool]) -> None:
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
                if isinstance(wrapper, PreToolValidationWrapper):
                    wrapped_kwargs = {**kwargs, "enable_validation": kwargs.get("enable_validation", True)}
                    wrapped_tool = wrapper.wrap_tool(wrapped_tool, **wrapped_kwargs)
                    # Ensure ValidatedTool has current tool specs
                    if isinstance(wrapped_tool, ValidatedTool):
                        wrapped_tool.tool_specs = wrapper.tool_specs
                else:
                    wrapped_tool = wrapper.wrap_tool(wrapped_tool, **kwargs)
        
        return wrapped_tool


# === Post Tool Processing Implementation ===

class PostToolProcessor(BaseTool):
    """A tool output processor to process tool outputs.

    This wrapper intercepts the tool execution output and
    if the tool output is a JSON, it invokes an ALTK component
    to extract information from the JSON by generating Python code.
    """

    name: str = Field(...)
    description: str = Field(...)
    wrapped_tool: BaseTool = Field(...)
    user_query: str = Field(...)
    agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor = Field(...)
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
            raise

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
        
    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        # Run the wrapped tool synchronously for now (can be enhanced for async later)
        return self._run(*args, **kwargs)

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

    def _get_altk_llm_object(self) -> Any:
        # Extract the LLM model and map it to altk model inputs
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
            llm_client = get_llm("litellm")
            llm_client_obj = llm_client(model_name=model_name, api_key=api_key)
        elif isinstance(llm_object, ChatOpenAI):
            model_name = llm_object.model_name
            api_key = llm_object.openai_api_key.get_secret_value()
            llm_client = get_llm("openai.sync")
            llm_client_obj = llm_client(model=model_name, api_key=api_key)
        else:
            logger.info("ALTK currently only supports OpenAI and Anthropic models through Langflow.")
            llm_client_obj = None

        return llm_client_obj

    def process_tool_response(self, tool_response: str, **_kwargs) -> str:
        logger.info("Calling process_tool_response of PostToolProcessor")
        tool_response_str = self._get_tool_response_str(tool_response)

        # First check if this looks like an error message with bullet points (SPARC rejection)
        if "❌" in tool_response_str or "•" in tool_response_str:
            logger.info("Detected error message with special characters, skipping JSON parsing")
            return tool_response_str

        try:
            # Only attempt to parse content that looks like JSON
            if (tool_response_str.startswith("{") and tool_response_str.endswith("}")) or \
               (tool_response_str.startswith("[") and tool_response_str.endswith("]")):
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
            llm_client_obj = self._get_altk_llm_object()
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


# === Pre Tool Validation Implementation ===

def _check_sparc_available():
    """Check if SPARC is available by attempting import. Cached after first call."""
    global SPARCReflectionRunInput, SPARCExecutionMode, Track
    global SPARCReflectionComponent, AgentPhase, ComponentConfig, get_llm
    
    if SPARCReflectionComponent is not None:
        return True  # Already successfully imported
    
    try:
        from altk.pre_tool_reflection_toolkit.core import (
            SPARCReflectionRunInput as _SPARCReflectionRunInput,
            SPARCExecutionMode as _SPARCExecutionMode,
            Track as _Track,
        )
        from altk.pre_tool_reflection_toolkit.sparc import (
            SPARCReflectionComponent as _SPARCReflectionComponent,
        )
        
        # Assign to module-level variables
        SPARCReflectionRunInput = _SPARCReflectionRunInput
        SPARCExecutionMode = _SPARCExecutionMode
        Track = _Track
        SPARCReflectionComponent = _SPARCReflectionComponent
        
        logger.info("✅ SPARC toolkit successfully imported and available")
        return True
    except ImportError as e:
        logger.warning(f"SPARC toolkit not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Error importing SPARC toolkit: {e}")
        return False



class ToolValidationCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for logging tool validation events.
    """
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called when a tool starts running."""
        tool_name = serialized.get("name", "unknown_tool")
        logger.info(f"Tool {tool_name} starting execution")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when a tool finishes running successfully."""
        logger.info("Tool execution completed successfully")
    
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Called when a tool encounters an error."""
        logger.info(f"Tool execution failed with error: {error}")




# === Combined Enhanced Agent Component ===

class EnhancedAgentComponent(AgentComponent):
    """Enhanced Agent with both pre-tool validation and post-tool processing capabilities.
    
    This agent combines the functionality of both ALTKAgent and AgentReflection components,
    implementing a modular pipeline for tool processing that can be extended with
    additional capabilities in the future.
    """
    
    display_name: str = "Enhanced Agent"
    description: str = "Advanced agent with both pre-tool validation and post-tool processing capabilities."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "zap"
    beta = True
    name = "EnhancedAgent"

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
        *AgentComponent.inputs,
        BoolInput(
            name="enable_tool_validation",
            display_name="Tool Validation",
            info="Validates tool calls using SPARC before execution.",
            value=True,
        ),
        BoolInput(
            name="enable_post_tool_reflection",
            display_name="Post Tool Processing",
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
        self._initialize_tool_wrappers()
    
    def _initialize_tool_wrappers(self):
        """Initialize tool wrappers based on enabled features."""
        # Add post-tool processing first (innermost wrapper)
        if self.enable_post_tool_reflection:
            post_processor = PostToolProcessingWrapper(
                response_processing_size_threshold=self.response_processing_size_threshold
            )
            self.pipeline_manager.add_wrapper(post_processor)
                
        # Add pre-tool validation second (outermost wrapper)
        if self.enable_tool_validation:
            pre_validator = PreToolValidationWrapper()
            self.pipeline_manager.add_wrapper(pre_validator)

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        """Run the agent with the enhanced tool pipeline.
        
        This method combines both pre-tool validation and post-tool processing
        capabilities based on the enabled features.
        
        Args:
            agent: The agent to run
            
        Returns:
            A message with the agent's response
        """
        # Prepare input and extract user query
        input_dict: dict[str, str | list[BaseMessage]] = {
            "input": self.input_value.to_lc_message() if isinstance(self.input_value, Message) else self.input_value
        }
        user_query = input_dict["input"].content if hasattr(input_dict["input"], "content") else input_dict["input"]
        
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
        
        # Process tools through the pipeline
        processed_tools = self.pipeline_manager.process_tools(
            self.tools or [], 
            agent=agent, 
            user_query=user_query,
            conversation_context=conversation_context,
            enable_validation=getattr(self, "enable_tool_validation", True)
        )
        
        # Set up the runnable agent
        if isinstance(agent, AgentExecutor):
            runnable = agent
            # Update the tools in the existing AgentExecutor
            runnable.tools = processed_tools
        else:
            # Create AgentExecutor from agent and tools
            handle_parsing_errors = hasattr(self, "handle_parsing_errors") and self.handle_parsing_errors
            verbose = hasattr(self, "verbose") and self.verbose
            max_iterations = hasattr(self, "max_iterations") and self.max_iterations
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=processed_tools,
                handle_parsing_errors=handle_parsing_errors,
                verbose=verbose,
                max_iterations=max_iterations,
                return_intermediate_steps=True,
            )

        # Set system prompt if available
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
            
        # Set chat history if available
        if hasattr(self, "chat_history") and self.chat_history:
            if isinstance(self.chat_history, Data):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            if all(isinstance(m, Message) for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages([m.to_data() for m in self.chat_history])

        # Handle image content in input
        if hasattr(input_dict["input"], "content") and isinstance(input_dict["input"].content, list):
            image_dicts = [item for item in input_dict["input"].content if item.get("type") == "image"]
            input_dict["input"].content = [item for item in input_dict["input"].content if item.get("type") != "image"]

            if "chat_history" not in input_dict:
                input_dict["chat_history"] = []
            if isinstance(input_dict["chat_history"], list):
                input_dict["chat_history"].extend(HumanMessage(content=[image_dict]) for image_dict in image_dicts)
            else:
                input_dict["chat_history"] = [HumanMessage(content=[image_dict]) for image_dict in image_dicts]

        # Get session ID
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        # Create agent message for tracking
        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=self.display_name or "Enhanced Agent",
            properties={"icon": "Zap", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )

        try:
            # Set up callbacks
            callbacks_to_be_used = [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]
            
            # Add validation callback if tool validation is enabled
            if hasattr(self, "enable_tool_validation") and self.enable_tool_validation:
                validation_handler = ToolValidationCallbackHandler()
                callbacks_to_be_used.append(validation_handler)

            # Run the agent with the enhanced tools
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": callbacks_to_be_used},
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
            logger.error(f"Error in agent execution: {e}")
            raise

        self.status = result
        return result