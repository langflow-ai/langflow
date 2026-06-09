"""A simple agent flow example for Langflow.

This script demonstrates how to set up a conversational agent using Langflow's
Agent component with web search capabilities.

Features:
- Uses the new flattened component access (cp.AgentComponent instead of deep imports)
- Configures logging to 'langflow.log' at INFO level
- Creates an agent with OpenAI GPT model
- Provides web search tools via URLComponent
- Connects ChatInput → Agent → ChatOutput

Usage:
    uv run lfx run simple_agent.py "How are you?"
"""

import os
from pathlib import Path

from lfx.graph import Graph
from lfx.log.logger import LogConfig

# Using the new flattened component access
from lfx import components as cp


async def get_graph() -> Graph:
    """Create and return the graph with async component initialization.

    This function properly handles async component initialization without
    blocking the module loading process. The script loader will detect this
    async function and handle it appropriately using run_until_complete.

    Returns:
        Graph: The configured graph with ChatInput → Agent → ChatOutput flow
    """
    log_config = LogConfig(
        log_level="INFO",
        log_file=Path("langflow.log"),
    )

    # Showcase the new flattened component access - no need for deep imports!
    chat_input = cp.ChatInput()
    agent = cp.AgentComponent()

    # Use URLComponent for web search capabilities
    url_component = cp.URLComponent()
    tools = await url_component.to_toolkit()

    agent.set(
        model_name="gpt-4o-mini",
        agent_llm="OpenAI",
        api_key=os.getenv("OPENAI_API_KEY"),
        input_value=chat_input.message_response,
        tools=tools,
    )
    chat_output = cp.ChatOutput().set(input_value=agent.message_response)

    return Graph(chat_input, chat_output, log_config=log_config)
