"""IBM WatsonX-specific tool calling logic.

This module contains all the specialized handling for IBM WatsonX models
which have different tool calling behavior compared to other LLMs.

The tool calling issues affect ALL models on the WatsonX platform,
not just Granite models. This includes:
- meta-llama models
- mistral models
- granite models
- any other model running through WatsonX
"""

import re

from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain.agents.output_parsers.tools import ToolsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from lfx.log.logger import logger

# Pattern to detect placeholder usage in tool arguments
PLACEHOLDER_PATTERN = re.compile(
    r"<[^>]*(?:result|value|output|response|data|from|extract|previous|current|date|input|query|search|tool)[^>]*>",
    re.IGNORECASE,
)


def is_watsonx_model(llm) -> bool:
    """Check if the LLM is an IBM WatsonX model (any model, not just Granite).

    This detects the provider (WatsonX) rather than a specific model,
    since tool calling issues affect all models on the WatsonX platform.
    """
    # Check class name for WatsonX (e.g., ChatWatsonx)
    class_name = type(llm).__name__.lower()
    if "watsonx" in class_name:
        return True

    # Fallback: check module name (e.g., langchain_ibm)
    module_name = getattr(type(llm), "__module__", "").lower()
    return "watsonx" in module_name or "langchain_ibm" in module_name


def is_granite_model(llm) -> bool:
    """Check if the LLM is an IBM Granite model.

    DEPRECATED: Use is_watsonx_model() instead.
    Kept for backwards compatibility.
    """
    model_id = getattr(llm, "model_id", getattr(llm, "model_name", ""))
    return "granite" in str(model_id).lower()


def _get_tool_schema_description(tool) -> str:
    """Extract a brief description of the tool's expected parameters.

    Returns empty string if schema extraction fails (graceful degradation).
    """
    if not hasattr(tool, "args_schema") or not tool.args_schema:
        return ""

    schema = tool.args_schema
    if not hasattr(schema, "model_fields"):
        return ""

    try:
        fields = schema.model_fields
        params = []
        for name, field in fields.items():
            required = field.is_required() if hasattr(field, "is_required") else True
            req_str = "(required)" if required else "(optional)"
            params.append(f"{name} {req_str}")
        return f"Parameters: {', '.join(params)}" if params else ""
    except (AttributeError, TypeError) as e:
        logger.debug(f"Could not extract schema for tool {getattr(tool, 'name', 'unknown')}: {e}")
        return ""


def get_enhanced_system_prompt(base_prompt: str, tools: list) -> str:
    """Enhance system prompt for WatsonX models with tool usage instructions."""
    if not tools or len(tools) <= 1:
        return base_prompt

    # Build detailed tool descriptions with their parameters
    tool_descriptions = []
    for t in tools:
        schema_desc = _get_tool_schema_description(t)
        if schema_desc:
            tool_descriptions.append(f"- {t.name}: {schema_desc}")
        else:
            tool_descriptions.append(f"- {t.name}")

    tools_section = "\n".join(tool_descriptions)

    # Note: "one tool at a time" is a WatsonX platform limitation, not a design choice.
    # WatsonX models don't reliably support parallel tool calls.
    enhancement = f"""

TOOL USAGE GUIDELINES:

1. ALWAYS call tools when you need information - never say "I cannot" or "I don't have access".
2. Call one tool at a time, then use its result before calling another tool.
3. Use ACTUAL values in tool arguments - never use placeholder syntax like <result-from-...>.
4. Each tool has specific parameters - use the correct ones for each tool.

AVAILABLE TOOLS:
{tools_section}"""

    return base_prompt + enhancement


def detect_placeholder_in_args(tool_calls: list) -> tuple[bool, str | None]:
    """Detect if any tool call contains placeholder syntax in its arguments."""
    if not tool_calls:
        return False, None

    for tool_call in tool_calls:
        args = tool_call.get("args", {})
        if isinstance(args, dict):
            for key, value in args.items():
                if isinstance(value, str) and PLACEHOLDER_PATTERN.search(value):
                    tool_name = tool_call.get("name", "unknown")
                    logger.warning(f"[IBM WatsonX] Detected placeholder: {tool_name}.{key}={value}")
                    return True, value
        elif isinstance(args, str) and PLACEHOLDER_PATTERN.search(args):
            logger.warning(f"[IBM WatsonX] Detected placeholder in args: {args}")
            return True, args
    return False, None


def _limit_to_single_tool_call(llm_response):
    """Limit response to single tool call (WatsonX platform limitation)."""
    if not hasattr(llm_response, "tool_calls") or not llm_response.tool_calls:
        return llm_response

    if len(llm_response.tool_calls) > 1:
        logger.debug(f"[WatsonX] Limiting {len(llm_response.tool_calls)} tool calls to 1")
        llm_response.tool_calls = [llm_response.tool_calls[0]]

    return llm_response


def _handle_placeholder_in_response(llm_response, messages, llm_auto):
    """Re-invoke with corrective message if placeholder syntax detected."""
    if not hasattr(llm_response, "tool_calls") or not llm_response.tool_calls:
        return llm_response

    has_placeholder, _ = detect_placeholder_in_args(llm_response.tool_calls)
    if not has_placeholder:
        return llm_response

    logger.warning("[WatsonX] Placeholder detected, requesting actual values")
    from langchain_core.messages import SystemMessage

    corrective_msg = SystemMessage(
        content="Provide your final answer using the actual values from previous tool results."
    )
    messages_list = list(messages.messages) if hasattr(messages, "messages") else list(messages)
    messages_list.append(corrective_msg)
    return llm_auto.invoke(messages_list)


def create_granite_agent(llm, tools: list, prompt: ChatPromptTemplate, forced_iterations: int = 2):
    """Create a tool calling agent for IBM WatsonX/Granite models.

    Why this exists: WatsonX models have platform-specific tool calling behavior:
    - With tool_choice='auto': Models often describe tools in text instead of calling them
    - With tool_choice='required': Models can't provide final answers (causes infinite loops)
    - Models only reliably support single tool calls per turn

    Solution: Dynamic switching between 'required' (to force tool use) and 'auto' (to allow answers).

    Args:
        llm: WatsonX language model instance
        tools: Available tools for the agent
        prompt: Chat prompt template
        forced_iterations: Iterations to force tool_choice='required' before allowing 'auto'

    Returns:
        Runnable agent chain compatible with AgentExecutor
    """
    if not hasattr(llm, "bind_tools"):
        msg = "WatsonX handler requires a language model with bind_tools support."
        raise ValueError(msg)

    llm_required = llm.bind_tools(tools or [], tool_choice="required")
    llm_auto = llm.bind_tools(tools or [], tool_choice="auto")

    def invoke(inputs: dict):
        intermediate_steps = inputs.get("intermediate_steps", [])
        num_steps = len(intermediate_steps)

        scratchpad = format_to_tool_messages(intermediate_steps)
        messages = prompt.invoke({**inputs, "agent_scratchpad": scratchpad})

        # Use 'required' for first N iterations, then 'auto' to allow final answers
        use_required = num_steps < forced_iterations
        llm_to_use = llm_required if use_required else llm_auto
        logger.debug(f"[WatsonX] Step {num_steps + 1}, tool_choice={'required' if use_required else 'auto'}")

        response = llm_to_use.invoke(messages)
        response = _limit_to_single_tool_call(response)
        return _handle_placeholder_in_response(response, messages, llm_auto)

    return RunnableLambda(invoke) | ToolsAgentOutputParser()


# Alias for backwards compatibility
create_watsonx_agent = create_granite_agent
