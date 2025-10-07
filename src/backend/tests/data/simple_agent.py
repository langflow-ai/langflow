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
from lfx.utils.async_helpers import run_until_complete

# Using the new flattened component access
from lfx import components as cp

log_config = LogConfig(
    log_level="INFO",
    log_file=Path("langflow.log"),
)

# Showcase the new flattened component access - no need for deep imports!
chat_input = cp.ChatInput()
agent = cp.AgentComponent()
url_component = cp.URLComponent()
tools = run_until_complete(url_component.to_toolkit())

agent.set(
    model_name="gpt-4o-mini",
    agent_llm="OpenAI",
    api_key=os.getenv("OPENAI_API_KEY"),
    input_value=chat_input.message_response,
    tools=tools,
)
chat_output = cp.ChatOutput().set(input_value=agent.message_response)

graph = Graph(chat_input, chat_output, log_config=log_config)
