"""
Test configuration and fixtures for langflow tests.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_components():
    """Sample components for testing."""
    return [
        {
            "id": "input",
            "type": "genesis:chat_input",
            "name": "Input",
            "description": "User input",
            "provides": [
                {"in": "agent", "useAs": "input", "description": "User input to agent"}
            ]
        },
        {
            "id": "agent",
            "type": "genesis:agent",
            "name": "Agent",
            "description": "Processing agent",
            "config": {
                "temperature": 0.1,
                "max_tokens": 1000
            },
            "provides": [
                {"in": "output", "useAs": "input", "description": "Agent response to output"}
            ]
        },
        {
            "id": "output",
            "type": "genesis:chat_output",
            "name": "Output",
            "description": "Response output"
        }
    ]


@pytest.fixture
def sample_tool_components():
    """Sample components with tools for testing."""
    return [
        {
            "id": "input",
            "type": "genesis:chat_input",
            "provides": [
                {"in": "agent", "useAs": "input", "description": "User input"}
            ]
        },
        {
            "id": "tool1",
            "type": "genesis:mcp_tool",
            "asTools": True,
            "config": {
                "tool_name": "test_tool"
            },
            "provides": [
                {"in": "agent", "useAs": "tools", "description": "MCP tool"}
            ]
        },
        {
            "id": "tool2",
            "type": "genesis:knowledge_hub_search",
            "asTools": True,
            "provides": [
                {"in": "agent", "useAs": "tools", "description": "Knowledge search"}
            ]
        },
        {
            "id": "agent",
            "type": "genesis:agent",
            "provides": [
                {"in": "output", "useAs": "input", "description": "Agent response"}
            ]
        },
        {
            "id": "output",
            "type": "genesis:chat_output"
        }
    ]


@pytest.fixture
def sample_specification_yaml():
    """Sample YAML specification for testing."""
    return """
name: Test Agent
description: Test specification for validation
version: 1.0.0
agentGoal: Test enhanced type compatibility validation

components:
  - id: input
    type: genesis:chat_input
    name: Input
    description: User input
    provides:
      - in: agent
        useAs: input
        description: User input to agent

  - id: agent
    type: genesis:agent
    name: Agent
    description: Processing agent
    config:
      temperature: 0.1
      max_tokens: 1000
    provides:
      - in: output
        useAs: input
        description: Agent response to output

  - id: output
    type: genesis:chat_output
    name: Output
    description: Response output
"""