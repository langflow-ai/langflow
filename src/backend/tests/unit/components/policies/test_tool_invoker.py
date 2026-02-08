from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.components.policies.guarded_tool import ToolInvoker
from mcp.types import CallToolResult
from pydantic import BaseModel


class Person(BaseModel):
    name: str
    age: int


class Address(BaseModel):
    street: str
    city: str
    zip_code: str


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_dict_result():
    """Test invoking a tool that returns a plain dict."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.ainvoke = AsyncMock(return_value={"result": "success", "data": 42})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("test_tool", {"arg1": "value1"}, dict)

    assert result == {"result": "success", "data": 42}
    tool.ainvoke.assert_called_once_with(input={"arg1": "value1"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_value_dict():
    """Test invoking a tool that returns a dict with 'value' key."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.ainvoke = AsyncMock(return_value={"value": {"name": "Alice", "age": 30}})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("test_tool", {"query": "person"}, dict)

    assert result == {"name": "Alice", "age": 30}
    tool.ainvoke.assert_called_once_with(input={"query": "person"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_call_tool_result():
    """Test invoking a tool that returns CallToolResult."""
    tool = MagicMock()
    tool.name = "test_tool"

    # Create a mock CallToolResult
    mock_result = MagicMock(spec=CallToolResult)
    mock_result.structuredContent = {"result": {"status": "ok", "count": 5}}
    tool.ainvoke = AsyncMock(return_value=mock_result)

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("test_tool", {"action": "count"}, dict)

    assert result == {"status": "ok", "count": 5}
    tool.ainvoke.assert_called_once_with(input={"action": "count"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_basemodel_return_type():
    """Test invoking a tool with BaseModel return type."""
    tool = MagicMock()
    tool.name = "get_person"
    tool.ainvoke = AsyncMock(return_value={"name": "Bob", "age": 25})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("get_person", {"id": 123}, Person)

    assert isinstance(result, Person)
    assert result.name == "Bob"
    assert result.age == 25
    tool.ainvoke.assert_called_once_with(input={"id": 123})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_basemodel_result():
    """Test invoking a tool that returns a BaseModel instance."""
    tool = MagicMock()
    tool.name = "get_address"

    # Tool returns a BaseModel instance
    address = Address(street="123 Main St", city="Springfield", zip_code="12345")
    tool.ainvoke = AsyncMock(return_value=address)

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("get_address", {"user_id": 456}, Address)

    assert isinstance(result, Address)
    assert result.street == "123 Main St"
    assert result.city == "Springfield"
    assert result.zip_code == "12345"
    tool.ainvoke.assert_called_once_with(input={"user_id": 456})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_int_return_type():
    """Test invoking a tool with int return type."""
    tool = MagicMock()
    tool.name = "count_items"
    tool.ainvoke = AsyncMock(return_value=42)

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("count_items", {"category": "books"}, int)

    assert result == 42
    assert isinstance(result, int)
    tool.ainvoke.assert_called_once_with(input={"category": "books"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_float_return_type():
    """Test invoking a tool with float return type."""
    tool = MagicMock()
    tool.name = "calculate_price"
    tool.ainvoke = AsyncMock(return_value=99.99)

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("calculate_price", {"item": "widget"}, float)

    assert result == 99.99
    assert isinstance(result, float)
    tool.ainvoke.assert_called_once_with(input={"item": "widget"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_str_return_type():
    """Test invoking a tool with str return type."""
    tool = MagicMock()
    tool.name = "get_message"
    tool.ainvoke = AsyncMock(return_value="Hello, World!")

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("get_message", {"lang": "en"}, str)

    assert result == "Hello, World!"
    assert isinstance(result, str)
    tool.ainvoke.assert_called_once_with(input={"lang": "en"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_bool_return_type():
    """Test invoking a tool with bool return type."""
    tool = MagicMock()
    tool.name = "is_valid"
    tool.ainvoke = AsyncMock(return_value=True)

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("is_valid", {"data": "test"}, bool)

    assert result is True
    assert isinstance(result, bool)
    tool.ainvoke.assert_called_once_with(input={"data": "test"})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_unknown_tool():
    """Test invoking a tool that doesn't exist."""
    tool = MagicMock()
    tool.name = "existing_tool"

    invoker = ToolInvoker([tool])

    with pytest.raises(ValueError, match="unknown tool nonexistent_tool"):
        await invoker.invoke("nonexistent_tool", {"arg": "value"}, dict)


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_empty_arguments():
    """Test invoking a tool with empty arguments."""
    tool = MagicMock()
    tool.name = "no_args_tool"
    tool.ainvoke = AsyncMock(return_value={"status": "ok"})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("no_args_tool", {}, dict)

    assert result == {"status": "ok"}
    tool.ainvoke.assert_called_once_with(input={})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_complex_arguments():
    """Test invoking a tool with complex nested arguments."""
    tool = MagicMock()
    tool.name = "complex_tool"
    complex_args = {
        "user": {"name": "Charlie", "age": 35},
        "settings": {"theme": "dark", "notifications": True},
        "items": [1, 2, 3, 4, 5],
    }
    tool.ainvoke = AsyncMock(return_value={"processed": True})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("complex_tool", complex_args, dict)

    assert result == {"processed": True}
    tool.ainvoke.assert_called_once_with(input=complex_args)


@pytest.mark.asyncio
async def test_tool_invoker_multiple_tools():
    """Test ToolInvoker with multiple tools and invoking different ones."""
    tool1 = MagicMock()
    tool1.name = "tool1"
    tool1.ainvoke = AsyncMock(return_value={"result": "from_tool1"})

    tool2 = MagicMock()
    tool2.name = "tool2"
    tool2.ainvoke = AsyncMock(return_value={"result": "from_tool2"})

    tool3 = MagicMock()
    tool3.name = "tool3"
    tool3.ainvoke = AsyncMock(return_value={"result": "from_tool3"})

    invoker = ToolInvoker([tool1, tool2, tool3])

    # Invoke each tool
    result1 = await invoker.invoke("tool1", {}, dict)
    result2 = await invoker.invoke("tool2", {}, dict)
    result3 = await invoker.invoke("tool3", {}, dict)

    assert result1 == {"result": "from_tool1"}
    assert result2 == {"result": "from_tool2"}
    assert result3 == {"result": "from_tool3"}

    tool1.ainvoke.assert_called_once()
    tool2.ainvoke.assert_called_once()
    tool3.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_tool_invoker_invoke_with_basemodel_in_value_dict():
    """Test invoking a tool that returns BaseModel wrapped in value dict."""
    tool = MagicMock()
    tool.name = "get_person_wrapped"

    # Tool returns a dict with 'value' containing a BaseModel
    person = Person(name="Diana", age=28)
    tool.ainvoke = AsyncMock(return_value={"value": person})

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("get_person_wrapped", {"id": 789}, Person)

    assert isinstance(result, Person)
    assert result.name == "Diana"
    assert result.age == 28
    tool.ainvoke.assert_called_once_with(input={"id": 789})


@pytest.mark.asyncio
async def test_tool_invoker_invoke_primitive_type_conversion():
    """Test that primitive types are properly converted from string results."""
    tool = MagicMock()
    tool.name = "string_number"
    tool.ainvoke = AsyncMock(return_value="123")

    invoker = ToolInvoker([tool])
    result = await invoker.invoke("string_number", {}, int)

    assert result == 123
    assert isinstance(result, int)


# Made with Bob
