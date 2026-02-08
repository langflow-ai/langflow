from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import StructuredTool
from lfx.components.policies.guarded_tool import GuardedTool
from pydantic import BaseModel
from toolguard.runtime import PolicyViolationException


class Person(BaseModel):
    name: str
    age: int


def my_function(person: Person) -> str:
    """Format a person's information as a string.

    Args:
        person: A Person object containing name and age.

    Returns:
        A formatted string with the person's name and age.
    """
    return f"{person.name} is {person.age} years old"


@pytest.mark.asyncio
async def test_guarded_tool_successful_execution():
    """Test GuardedTool with successful policy validation."""
    lc_tool = StructuredTool.from_function(my_function)
    guarded_tool = GuardedTool(lc_tool, [lc_tool], Path())

    # Mock the toolguard context manager and guard_toolcall
    mock_toolguard = MagicMock()
    mock_toolguard.guard_toolcall = AsyncMock()

    with patch("lfx.components.policies.guarded_tool.load_toolguards") as mock_load:
        mock_load.return_value.__enter__.return_value = mock_toolguard
        mock_load.return_value.__exit__.return_value = None

        # Test with dict input
        result = await guarded_tool.arun({"person": {"name": "Alice", "age": 30}})

        # Verify guard_toolcall was called
        mock_toolguard.guard_toolcall.assert_called_once()
        assert "Alice is 30 years old" in result


@pytest.mark.asyncio
async def test_guarded_tool_policy_violation():
    """Test GuardedTool when policy is violated."""
    lc_tool = StructuredTool.from_function(my_function)
    guarded_tool = GuardedTool(lc_tool, [lc_tool], Path())

    # Mock the toolguard to raise PolicyViolationException
    mock_toolguard = MagicMock()
    mock_toolguard.guard_toolcall = AsyncMock(side_effect=PolicyViolationException("Age must be under 25"))

    with patch("lfx.components.policies.guarded_tool.load_toolguards") as mock_load:
        mock_load.return_value.__enter__.return_value = mock_toolguard
        mock_load.return_value.__exit__.return_value = None

        # Test with dict input that violates policy
        result = await guarded_tool.arun({"person": {"name": "Bob", "age": 30}})

        # Verify the error response structure
        assert result["ok"] is False
        assert result["error"]["type"] == "PolicyViolationException"
        assert result["error"]["code"] == "FAILURE"
        assert "Age must be under 25" in result["error"]["message"]
        assert result["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_guarded_tool_parse_input_string():
    """Test parse_input with string input."""
    lc_tool = StructuredTool.from_function(my_function)
    guarded_tool = GuardedTool(lc_tool, [lc_tool], Path())

    # Test JSON string
    result = guarded_tool.parse_input('{"name": "Charlie", "age": 25}')
    assert result == {"name": "Charlie", "age": 25}

    # Test non-JSON string (should wrap in dict)
    result = guarded_tool.parse_input("plain text")
    assert result == {"input": "plain text"}


@pytest.mark.asyncio
async def test_guarded_tool_parse_input_toolcall():
    """Test parse_input with ToolCall dict format."""
    lc_tool = StructuredTool.from_function(my_function)
    guarded_tool = GuardedTool(lc_tool, [lc_tool], Path())

    # Test with args as JSON string
    result = guarded_tool.parse_input({"args": '{"name": "Dave", "age": 35}'})
    assert result == {"name": "Dave", "age": 35}

    # Test with args as dict
    result = guarded_tool.parse_input({"args": {"name": "Eve", "age": 40}})
    assert result == {"name": "Eve", "age": 40}

    # Test with args as non-JSON string
    result = guarded_tool.parse_input({"args": "invalid json"})
    assert result == {"input": "invalid json"}


def test_guarded_tool_run_not_implemented():
    """Test that sync run() raises NotImplementedError."""
    lc_tool = StructuredTool.from_function(my_function)
    guarded_tool = GuardedTool(lc_tool, [lc_tool], Path())

    with pytest.raises(NotImplementedError, match="consider calling the async version arun"):
        guarded_tool.run({"person": {"name": "Test", "age": 20}})
