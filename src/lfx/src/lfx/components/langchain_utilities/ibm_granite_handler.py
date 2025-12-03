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
    """Extract a brief description of the tool's expected parameters."""
    try:
        # Try to get the tool's input schema
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema = tool.args_schema
            if hasattr(schema, "model_fields"):
                fields = schema.model_fields
                params = []
                for name, field in fields.items():
                    required = field.is_required() if hasattr(field, "is_required") else True
                    req_str = "(required)" if required else "(optional)"
                    params.append(f"{name} {req_str}")
                return f"Parameters: {', '.join(params)}" if params else ""
    except Exception:  # noqa: BLE001
        return ""
    else:
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

    enhancement = f"""

IMPORTANT INSTRUCTIONS FOR TOOL USAGE:

1. ALWAYS call tools when you need information - never say "I cannot" or "I don't have access".
2. Call ONE tool at a time, wait for the result, then decide your next action.
3. NEVER use placeholder syntax like <result-from-...> or <previous-value> in tool arguments.
4. After getting tool results, extract the ACTUAL values and use them directly.
5. For date calculations, compute the result yourself and include it in your final answer.
6. CRITICAL: Each tool has DIFFERENT parameters. Use the CORRECT parameters for each tool.

AVAILABLE TOOLS AND THEIR PARAMETERS:
{tools_section}

Remember: Use the correct parameter names for each tool. Do not mix parameters between tools."""

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


def create_granite_agent(llm, tools: list, prompt: ChatPromptTemplate, forced_iterations: int = 2):
    """Create a tool calling agent optimized for IBM WatsonX models.

    IBM WatsonX models (including Granite, Llama, Mistral, etc.) have issues with tool calling:
    - tool_choice='auto': Model outputs text descriptions instead of actual tool calls
    - tool_choice='required': Model can't provide final answers (infinite loop)
    - Some models only support single tool calls at once

    This uses dynamic tool_choice switching to solve both issues.

    Args:
        llm: The language model instance (any WatsonX model)
        tools: List of tools available to the agent
        prompt: The chat prompt template
        forced_iterations: Number of iterations to force tool_choice='required'

    Returns:
        A Runnable agent chain
    """
    if not hasattr(llm, "bind_tools"):
        msg = "IBM WatsonX handler requires a language model with bind_tools support."
        raise ValueError(msg)

    # Create LLM variants with different tool_choice settings
    # Note: WatsonX doesn't support parallel_tool_calls parameter, we handle multiple
    # tool calls manually by keeping only the first one
    llm_required = llm.bind_tools(tools or [], tool_choice="required")
    llm_auto = llm.bind_tools(tools or [], tool_choice="auto")

    def dynamic_invoke(inputs: dict):
        """Dynamically choose tool_choice based on iteration count."""
        intermediate_steps = inputs.get("intermediate_steps", [])
        num_steps = len(intermediate_steps)

        inputs_with_scratchpad = {**inputs, "agent_scratchpad": format_to_tool_messages(intermediate_steps)}
        messages = prompt.invoke(inputs_with_scratchpad)

        # Force tool calls for first N iterations, then allow final answers
        if num_steps < forced_iterations:
            logger.info(f"[IBM WatsonX] Iteration {num_steps + 1} - tool_choice='required'")
            llm_response = llm_required.invoke(messages)
        else:
            logger.info(f"[IBM WatsonX] Iteration {num_steps + 1} - tool_choice='auto'")
            llm_response = llm_auto.invoke(messages)

        # Handle multiple tool calls - some WatsonX models only support single tool calls
        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            if len(llm_response.tool_calls) > 1:
                num_calls = len(llm_response.tool_calls)
                logger.warning(f"[IBM WatsonX] Multiple tool calls detected ({num_calls}), keeping first")
                # Keep only the first tool call
                llm_response.tool_calls = [llm_response.tool_calls[0]]

            # Handle placeholder detection - force final answer if detected
            has_placeholder, _ = detect_placeholder_in_args(llm_response.tool_calls)
            if has_placeholder:
                logger.warning("[IBM WatsonX] Placeholder detected, forcing final answer")
                from langchain_core.messages import SystemMessage

                corrective_msg = SystemMessage(
                    content=(
                        "STOP! Do not use placeholders. Provide your final answer NOW "
                        "based on the information you already have."
                    )
                )
                messages_list = list(messages.messages) if hasattr(messages, "messages") else list(messages)
                messages_list.append(corrective_msg)
                llm_response = llm_auto.invoke(messages_list)

        return llm_response

    logger.info("[IBM WatsonX] Created agent with dynamic tool_choice")
    return RunnableLambda(dynamic_invoke) | ToolsAgentOutputParser()


# Alias for backwards compatibility
create_watsonx_agent = create_granite_agent
