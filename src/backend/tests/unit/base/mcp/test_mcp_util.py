"""Unit tests for MCP utility functions.

This test suite validates the MCP utility functions including:
- Session management
- Header validation and processing
- Utility functions for name sanitization and schema conversion
"""

import re
import shutil
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.mcp import util
from lfx.base.mcp.util import (
    MCPSessionManager,
    MCPSseClient,
    MCPStdioClient,
    MCPStreamableHttpClient,
    _process_headers,
    validate_headers,
)


class TestMCPSessionManager:
    @pytest.fixture
    async def session_manager(self):
        """Create a session manager and clean it up after the test."""
        manager = MCPSessionManager()
        yield manager
        # Clean up after test
        await manager.cleanup_all()

    async def test_session_caching(self, session_manager):
        """Test that sessions are properly cached and reused."""
        context_id = "test_context"
        connection_params = MagicMock()
        transport_type = "stdio"

        # Create a mock session that will appear healthy
        mock_session = AsyncMock()
        mock_session._write_stream = MagicMock()
        mock_session._write_stream._closed = False

        # Create a mock task that appears to be running
        mock_task = AsyncMock()
        mock_task.done = MagicMock(return_value=False)

        with (
            patch.object(session_manager, "_create_stdio_session") as mock_create,
            patch.object(session_manager, "_validate_session_connectivity", return_value=True),
        ):
            mock_create.return_value = (mock_session, mock_task)

            # First call should create session
            session1 = await session_manager.get_session(context_id, connection_params, transport_type)

            # Second call should return cached session without creating new one
            session2 = await session_manager.get_session(context_id, connection_params, transport_type)

            assert session1 == session2
            assert session1 == mock_session
            # Should only create once since the second call should use the cached session
            mock_create.assert_called_once()

    async def test_session_cleanup(self, session_manager):
        """Test session cleanup functionality."""
        context_id = "test_context"
        server_key = "test_server"
        session_id = "test_session"

        # Add a session to the manager with proper mock setup using new structure
        mock_task = AsyncMock()
        mock_task.done = MagicMock(return_value=False)  # Use MagicMock for sync method
        mock_task.cancel = MagicMock()  # Use MagicMock for sync method

        # Set up the new session structure
        session_manager.sessions_by_server[server_key] = {
            "sessions": {session_id: {"session": AsyncMock(), "task": mock_task, "type": "stdio", "last_used": 0}},
            "last_cleanup": 0,
        }

        # Set up mapping for backwards compatibility
        session_manager._context_to_session[context_id] = (server_key, session_id)

        await session_manager._cleanup_session(context_id)

        # Should cancel the task and remove from sessions
        mock_task.cancel.assert_called_once()
        assert session_id not in session_manager.sessions_by_server[server_key]["sessions"]

    async def test_server_switch_detection(self, session_manager):
        """Test that server switches are properly detected and handled."""
        context_id = "test_context"

        # First server
        server1_params = MagicMock()
        server1_params.command = "server1"

        # Second server
        server2_params = MagicMock()
        server2_params.command = "server2"

        with (
            patch.object(session_manager, "_create_stdio_session") as mock_create,
            patch.object(session_manager, "_validate_session_connectivity", return_value=True),
        ):
            mock_session1 = AsyncMock()
            mock_session2 = AsyncMock()
            mock_task1 = AsyncMock()
            mock_task2 = AsyncMock()
            mock_create.side_effect = [(mock_session1, mock_task1), (mock_session2, mock_task2)]

            # First connection
            session1 = await session_manager.get_session(context_id, server1_params, "stdio")

            # Switch to different server should create new session
            session2 = await session_manager.get_session(context_id, server2_params, "stdio")

            assert session1 != session2
            assert mock_create.call_count == 2


class TestHeaderValidation:
    """Test the header validation functionality."""

    def test_validate_headers_valid_input(self):
        """Test header validation with valid headers."""
        headers = {"Authorization": "Bearer token123", "Content-Type": "application/json", "X-API-Key": "secret-key"}

        result = validate_headers(headers)

        # Headers should be normalized to lowercase
        expected = {"authorization": "Bearer token123", "content-type": "application/json", "x-api-key": "secret-key"}
        assert result == expected

    def test_validate_headers_empty_input(self):
        """Test header validation with empty/None input."""
        assert validate_headers({}) == {}
        assert validate_headers(None) == {}

    def test_validate_headers_invalid_names(self):
        """Test header validation with invalid header names."""
        headers = {
            "Invalid Header": "value",  # spaces not allowed
            "Header@Name": "value",  # @ not allowed
            "Header Name": "value",  # spaces not allowed
            "Valid-Header": "value",  # this should pass
        }

        result = validate_headers(headers)

        # Only the valid header should remain
        assert result == {"valid-header": "value"}

    def test_validate_headers_sanitize_values(self):
        """Test header value sanitization."""
        headers = {
            "Authorization": "Bearer \x00token\x1f with\r\ninjection",
            "Clean-Header": "  clean value  ",
            "Empty-After-Clean": "\x00\x01\x02",
            "Tab-Header": "value\twith\ttabs",  # tabs should be preserved
        }

        result = validate_headers(headers)

        # Control characters should be removed, whitespace trimmed
        # Header with injection attempts should be skipped
        expected = {"clean-header": "clean value", "tab-header": "value\twith\ttabs"}
        assert result == expected

    def test_validate_headers_non_string_values(self):
        """Test header validation with non-string values."""
        headers = {"String-Header": "valid", "Number-Header": 123, "None-Header": None, "List-Header": ["value"]}

        result = validate_headers(headers)

        # Only string headers should remain
        assert result == {"string-header": "valid"}

    def test_validate_headers_injection_attempts(self):
        """Test header validation against injection attempts."""
        headers = {
            "Injection1": "value\r\nInjected-Header: malicious",
            "Injection2": "value\nX-Evil: attack",
            "Safe-Header": "safe-value",
        }

        result = validate_headers(headers)

        # Injection attempts should be filtered out
        assert result == {"safe-header": "safe-value"}


class TestStreamableHTTPHeaderIntegration:
    """Integration test to verify headers are properly passed through the entire StreamableHTTP flow."""

    async def test_headers_processing(self):
        """Test that headers flow properly from server config through to StreamableHTTP client connection."""
        # Test the header processing function directly
        headers_input = [
            {"key": "Authorization", "value": "Bearer test-token"},
            {"key": "X-API-Key", "value": "secret-key"},
        ]

        expected_headers = {
            "authorization": "Bearer test-token",  # normalized to lowercase
            "x-api-key": "secret-key",
        }

        # Test _process_headers function with validation
        processed_headers = _process_headers(headers_input)
        assert processed_headers == expected_headers

        # Test different input formats
        # Test dict input with validation
        dict_headers = {"Authorization": "Bearer dict-token", "Invalid Header": "bad"}
        result = _process_headers(dict_headers)
        # Invalid header should be filtered out, valid header normalized
        assert result == {"authorization": "Bearer dict-token"}

        # Test None input
        assert _process_headers(None) == {}

        # Test empty list
        assert _process_headers([]) == {}

        # Test malformed list
        malformed_headers = [{"key": "Auth"}, {"value": "token"}]  # Missing value/key
        assert _process_headers(malformed_headers) == {}

        # Test list with invalid header names
        invalid_headers = [
            {"key": "Valid-Header", "value": "good"},
            {"key": "Invalid Header", "value": "bad"},  # spaces not allowed
        ]
        result = _process_headers(invalid_headers)
        assert result == {"valid-header": "good"}

    async def test_streamable_http_client_header_storage(self):
        """Test that SSE client properly stores headers in connection params."""
        streamable_http_client = MCPStreamableHttpClient()
        test_url = "http://test.url"
        test_headers = {"Authorization": "Bearer test123", "Custom": "value"}

        # Test that headers are properly stored in connection params
        # Set connection params as a dict like the implementation expects
        streamable_http_client._connection_params = {
            "url": test_url,
            "headers": test_headers,
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
        }

        # Verify headers are stored
        assert streamable_http_client._connection_params["url"] == test_url
        assert streamable_http_client._connection_params["headers"] == test_headers


class TestFieldNameConversion:
    """Test camelCase to snake_case field name conversion functionality."""

    def test_camel_to_snake_basic(self):
        """Test basic camelCase to snake_case conversion."""
        assert util._camel_to_snake("weatherMain") == "weather_main"
        assert util._camel_to_snake("topN") == "top_n"
        assert util._camel_to_snake("firstName") == "first_name"
        assert util._camel_to_snake("lastName") == "last_name"

    def test_camel_to_snake_edge_cases(self):
        """Test edge cases for camelCase conversion."""
        # Already snake_case should remain unchanged
        assert util._camel_to_snake("snake_case") == "snake_case"
        assert util._camel_to_snake("already_snake") == "already_snake"

        # Single word should remain unchanged
        assert util._camel_to_snake("simple") == "simple"
        assert util._camel_to_snake("UPPER") == "upper"

        # Multiple consecutive capitals
        assert util._camel_to_snake("XMLHttpRequest") == "xmlhttp_request"
        assert util._camel_to_snake("HTTPSConnection") == "httpsconnection"

        # Numbers
        assert util._camel_to_snake("version2Beta") == "version2_beta"
        assert util._camel_to_snake("test123Value") == "test123_value"

    def test_convert_field_names_exact_match(self):
        """Test field name conversion when fields already match schema."""
        from pydantic import Field, create_model

        # Create test schema with snake_case fields
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
        )

        # Input with exact field names should pass through unchanged
        input_args = {"weather_main": "Snow", "top_n": 6}
        result = util._convert_camel_case_to_snake_case(input_args, test_schema)

        assert result == {"weather_main": "Snow", "top_n": 6}

    def test_convert_field_names_camel_to_snake(self):
        """Test field name conversion from camelCase to snake_case."""
        from pydantic import Field, create_model

        # Create test schema with snake_case fields
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
            user_id=(str, Field(..., description="User identifier")),
        )

        # Input with camelCase field names
        input_args = {"weatherMain": "Snow", "topN": 6, "userId": "user123"}
        result = util._convert_camel_case_to_snake_case(input_args, test_schema)

        assert result == {"weather_main": "Snow", "top_n": 6, "user_id": "user123"}

    def test_convert_field_names_mixed_case(self):
        """Test field name conversion with mixed naming conventions."""
        from pydantic import Field, create_model

        # Create test schema with mixed field names
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            topN=(int, Field(..., description="Number of results")),  # Already camelCase in schema
            user_count=(int, Field(..., description="User count")),
        )

        # Input with mixed naming
        input_args = {"weatherMain": "Snow", "topN": 6, "user_count": 42}
        result = util._convert_camel_case_to_snake_case(input_args, test_schema)

        # weather_main should be converted, topN should match exactly, user_count should match exactly
        assert result == {"weather_main": "Snow", "topN": 6, "user_count": 42}

    def test_convert_field_names_no_match(self):
        """Test field name conversion with fields that don't match schema."""
        from pydantic import Field, create_model

        # Create test schema
        test_schema = create_model("TestSchema", expected_field=(str, Field(..., description="Expected field")))

        # Input with unrecognized field names
        input_args = {"unknownField": "value", "anotherField": "value2"}
        result = util._convert_camel_case_to_snake_case(input_args, test_schema)

        # Fields that don't match should be kept as-is (validation will catch errors)
        assert result == {"unknownField": "value", "anotherField": "value2"}

    def test_convert_field_names_empty_input(self):
        """Test field name conversion with empty input."""
        from pydantic import Field, create_model

        test_schema = create_model("TestSchema", test_field=(str, Field(..., description="Test field")))

        # Empty input should return empty result
        result = util._convert_camel_case_to_snake_case({}, test_schema)
        assert result == {}

    def test_field_conversion_in_tool_validation(self):
        """Test that field conversion works end-to-end with Pydantic validation."""
        from pydantic import Field, create_model

        # Create test schema matching the original error case
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of top results")),
        )

        # Original error case: camelCase input
        input_args = {"weatherMain": "Snow", "topN": 6}
        converted_args = util._convert_camel_case_to_snake_case(input_args, test_schema)

        # Should validate successfully with converted field names
        validated = test_schema.model_validate(converted_args)
        assert validated.weather_main == "Snow"
        assert validated.top_n == 6
        assert validated.model_dump() == {"weather_main": "Snow", "top_n": 6}

    def test_field_conversion_preserves_values(self):
        """Test that field conversion preserves all value types correctly."""
        from pydantic import Field, create_model

        test_schema = create_model(
            "TestSchema",
            string_field=(str, Field(...)),
            int_field=(int, Field(...)),
            bool_field=(bool, Field(...)),
            list_field=(list, Field(...)),
            dict_field=(dict, Field(...)),
        )

        input_args = {
            "stringField": "test_string",
            "intField": 42,
            "boolField": True,
            "listField": [1, 2, 3],
            "dictField": {"nested": "value"},
        }

        result = util._convert_camel_case_to_snake_case(input_args, test_schema)

        expected = {
            "string_field": "test_string",
            "int_field": 42,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"nested": "value"},
        }

        assert result == expected

    def test_json_schema_alias_functionality(self):
        """Test that JSON schema creation includes aliases for camelCase field names."""
        from lfx.schema.json_schema import create_input_schema_from_json_schema
        from pydantic import ValidationError

        # Create a JSON schema with snake_case field names
        test_schema = {
            "type": "object",
            "properties": {
                "weather_main": {"type": "string", "description": "Main weather condition"},
                "top_n": {"type": "integer", "description": "Number of results"},
                "user_id": {"type": "string", "description": "User identifier"},
            },
            "required": ["weather_main", "top_n"],
        }

        # Create the Pydantic model using our function
        input_schema = create_input_schema_from_json_schema(test_schema)

        # Test with snake_case field names (should work)
        result1 = input_schema(weather_main="Rain", top_n=8)
        assert result1.weather_main == "Rain"
        assert result1.top_n == 8

        # Test with camelCase field names (should also work due to aliases)
        result2 = input_schema(weatherMain="Rain", topN=8)
        assert result2.weather_main == "Rain"
        assert result2.top_n == 8

        # Test with mixed case field names (should work)
        result3 = input_schema(weatherMain="Rain", top_n=8, userId="user123")
        assert result3.weather_main == "Rain"
        assert result3.top_n == 8
        assert result3.user_id == "user123"

        # Test validation error (should fail with missing required field)
        with pytest.raises(ValidationError):
            input_schema(weatherMain="Rain")  # Missing topN/top_n

    @pytest.mark.asyncio
    async def test_tool_empty_arguments_error_handling(self):
        """Test that tools provide helpful error messages when called with no arguments."""
        from unittest.mock import AsyncMock

        from lfx.schema.json_schema import create_input_schema_from_json_schema

        # Create a JSON schema with required fields
        test_schema = {
            "type": "object",
            "properties": {
                "weather_main": {"type": "string", "description": "Main weather condition"},
                "top_n": {"type": "integer", "description": "Number of results"},
            },
            "required": ["weather_main", "top_n"],
        }

        # Create the Pydantic model using our function
        input_schema = create_input_schema_from_json_schema(test_schema)

        # Create a mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="Success")

        # Create the tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", input_schema, mock_client)

        # Test that calling with no arguments gives a helpful error message
        with pytest.raises(ValueError, match="requires arguments but none were provided") as exc_info:
            await tool_coroutine()

        error_msg = str(exc_info.value)
        assert "test_tool" in error_msg
        assert "requires arguments but none were provided" in error_msg
        assert "weather_main" in error_msg
        assert "top_n" in error_msg

        # Test that calling with correct arguments works
        result = await tool_coroutine(weather_main="Rain", top_n=8)
        assert result == "Success"


class TestToolExecutionWithFieldConversion:
    """Test that field name conversion works in actual tool execution."""

    def test_create_tool_coroutine_with_camel_case_fields(self):
        """Test that create_tool_coroutine handles camelCase field conversion."""
        from unittest.mock import AsyncMock

        from pydantic import Field, create_model

        # Create test schema with snake_case fields
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
        )

        # Mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="tool_result")

        # Create tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", test_schema, mock_client)

        # Test that it's actually a coroutine function
        import asyncio

        assert asyncio.iscoroutinefunction(tool_coroutine)

    def test_create_tool_func_with_camel_case_fields(self):
        """Test that create_tool_func handles camelCase field conversion."""
        from unittest.mock import AsyncMock, MagicMock

        from pydantic import Field, create_model

        # Create test schema with snake_case fields
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
        )

        # Mock client with async run_tool method
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="tool_result")

        # Create tool function
        tool_func = util.create_tool_func("test_tool", test_schema, mock_client)

        # Mock the event loop
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(return_value="tool_result")

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Test with camelCase arguments
            result = tool_func(weatherMain="Snow", topN=6)

            assert result == "tool_result"
            # Verify that run_until_complete was called
            mock_loop.run_until_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_coroutine_field_conversion_end_to_end(self):
        """Test end-to-end field conversion in tool coroutine."""
        from unittest.mock import AsyncMock

        from pydantic import Field, create_model

        # Create test schema with snake_case fields (matching original error case)
        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
        )

        # Mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="success")

        # Create tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", test_schema, mock_client)

        # Test with camelCase keyword arguments (the problematic case)
        result = await tool_coroutine(weatherMain="Snow", topN=6)

        assert result == "success"
        # Verify client was called with converted field names
        mock_client.run_tool.assert_called_once_with("test_tool", arguments={"weather_main": "Snow", "top_n": 6})

    @pytest.mark.asyncio
    async def test_tool_coroutine_positional_args_no_conversion(self):
        """Test that positional arguments work correctly without field conversion."""
        from unittest.mock import AsyncMock

        from pydantic import Field, create_model

        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
        )

        # Mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="success")

        # Create tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", test_schema, mock_client)

        # Test with positional arguments
        result = await tool_coroutine("Snow", 6)

        assert result == "success"
        # Verify client was called with correct field mapping
        mock_client.run_tool.assert_called_once_with("test_tool", arguments={"weather_main": "Snow", "top_n": 6})

    @pytest.mark.asyncio
    async def test_tool_coroutine_mixed_args_and_conversion(self):
        """Test mixed positional and keyword arguments with field conversion."""
        from unittest.mock import AsyncMock

        from pydantic import Field, create_model

        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
            user_id=(str, Field(..., description="User ID")),
        )

        # Mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="success")

        # Create tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", test_schema, mock_client)

        # Test with one positional arg and camelCase keyword args
        result = await tool_coroutine("Snow", topN=6, userId="user123")

        assert result == "success"
        # Verify field names were properly converted
        mock_client.run_tool.assert_called_once_with(
            "test_tool", arguments={"weather_main": "Snow", "top_n": 6, "user_id": "user123"}
        )

    @pytest.mark.asyncio
    async def test_tool_coroutine_validation_error_with_conversion(self):
        """Test that validation errors are properly handled after field conversion."""
        from unittest.mock import AsyncMock

        from pydantic import Field, create_model

        test_schema = create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Required field")),
            top_n=(int, Field(..., description="Required field")),
        )

        # Mock client
        mock_client = AsyncMock()

        # Create tool coroutine
        tool_coroutine = util.create_tool_coroutine("test_tool", test_schema, mock_client)

        # Test with missing required field (should fail validation even after conversion)
        with pytest.raises(ValueError, match="Invalid input"):
            await tool_coroutine(weatherMain="Snow")  # Missing topN/top_n

    def test_tool_func_field_conversion_sync(self):
        """Test that create_tool_func handles field conversion in sync context."""
        from unittest.mock import AsyncMock, MagicMock

        from pydantic import Field, create_model

        test_schema = create_model(
            "TestSchema",
            user_name=(str, Field(..., description="User name")),
            max_results=(int, Field(..., description="Maximum results")),
        )

        # Mock client
        mock_client = AsyncMock()
        mock_client.run_tool = AsyncMock(return_value="sync_result")

        # Create tool function
        tool_func = util.create_tool_func("test_tool", test_schema, mock_client)

        # Mock asyncio.get_event_loop
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(return_value="sync_result")

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Test with camelCase fields
            result = tool_func(userName="testuser", maxResults=10)

            assert result == "sync_result"
            mock_loop.run_until_complete.assert_called_once()


class TestMCPUtilityFunctions:
    """Test utility functions from util.py that don't have dedicated test classes."""

    def test_sanitize_mcp_name(self):
        """Test MCP name sanitization."""
        assert util.sanitize_mcp_name("Test Name 123") == "test_name_123"
        assert util.sanitize_mcp_name("  ") == ""
        assert util.sanitize_mcp_name("123abc") == "_123abc"
        assert util.sanitize_mcp_name("Tést-😀-Námé") == "test_name"
        assert util.sanitize_mcp_name("a" * 100) == "a" * 46

    def test_get_unique_name(self):
        """Test unique name generation."""
        names = {"foo", "foo_1"}
        assert util.get_unique_name("foo", 10, names) == "foo_2"
        assert util.get_unique_name("bar", 10, names) == "bar"
        assert util.get_unique_name("longname", 4, {"long"}) == "lo_1"

    def test_is_valid_key_value_item(self):
        """Test key-value item validation."""
        assert util._is_valid_key_value_item({"key": "a", "value": "b"}) is True
        assert util._is_valid_key_value_item({"key": "a"}) is False
        assert util._is_valid_key_value_item(["key", "value"]) is False
        assert util._is_valid_key_value_item(None) is False

    def test_validate_node_installation(self):
        """Test Node.js installation validation."""
        if shutil.which("node"):
            assert util._validate_node_installation("npx something") == "npx something"
        else:
            with pytest.raises(ValueError, match=re.escape("Node.js is not installed")):
                util._validate_node_installation("npx something")
        assert util._validate_node_installation("echo test") == "echo test"

    def test_create_input_schema_from_json_schema(self):
        """Test JSON schema to Pydantic model conversion."""
        schema = {
            "type": "object",
            "properties": {
                "foo": {"type": "string", "description": "desc"},
                "bar": {"type": "integer"},
            },
            "required": ["foo"],
        }
        model_class = util.create_input_schema_from_json_schema(schema)
        instance = model_class(foo="abc", bar=1)
        assert instance.foo == "abc"
        assert instance.bar == 1

        with pytest.raises(Exception):  # noqa: B017, PT011
            model_class(bar=1)  # missing required field

    @pytest.mark.asyncio
    async def test_validate_connection_params(self):
        """Test connection parameter validation."""
        # Valid parameters
        await util._validate_connection_params("Stdio", command="echo test")
        await util._validate_connection_params("SSE", url="http://test")

        # Invalid parameters
        with pytest.raises(ValueError, match="Command is required for Stdio mode"):
            await util._validate_connection_params("Stdio", command=None)
        with pytest.raises(ValueError, match="URL is required for SSE mode"):
            await util._validate_connection_params("SSE", url=None)
        with pytest.raises(ValueError, match="Invalid mode"):
            await util._validate_connection_params("InvalidMode")

    @pytest.mark.asyncio
    async def test_get_flow_snake_case_mocked(self):
        """Test flow lookup by snake case name with mocked session."""

        class DummyFlow:
            def __init__(self, name: str, user_id: str, *, is_component: bool = False, action_name: str | None = None):
                self.name = name
                self.user_id = user_id
                self.is_component = is_component
                self.action_name = action_name

        class DummyExec:
            def __init__(self, flows: list[DummyFlow]):
                self._flows = flows

            def all(self):
                return self._flows

        class DummySession:
            def __init__(self, flows: list[DummyFlow]):
                self._flows = flows

            async def exec(self, stmt):  # noqa: ARG002
                return DummyExec(self._flows)

        user_id = "123e4567-e89b-12d3-a456-426614174000"
        flows = [DummyFlow("Test Flow", user_id), DummyFlow("Other", user_id)]

        # Should match sanitized name
        result = await util.get_flow_snake_case(util.sanitize_mcp_name("Test Flow"), user_id, DummySession(flows))
        assert result is flows[0]

        # Should return None if not found
        result = await util.get_flow_snake_case("notfound", user_id, DummySession(flows))
        assert result is None


@pytest.mark.skip(reason="Skipping MCPStdioClientWithEverythingServer tests.")
class TestMCPStdioClientWithEverythingServer:
    """Test MCPStdioClient with the Everything MCP server."""

    @pytest.fixture
    def stdio_client(self):
        """Create a stdio client for testing."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    @pytest.mark.skipif(
        sys.version_info >= (3, 13),
        reason="Temporarily disabled on Python 3.13 due to frequent timeouts with MCP Everything server",
    )
    async def test_connect_to_everything_server(self, stdio_client):
        """Test connecting to the Everything MCP server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Verify tools were returned
            assert len(tools) > 0

            # Find the echo tool
            echo_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "echo":
                    echo_tool = tool
                    break

            assert echo_tool is not None, "Echo tool not found in server tools"
            assert echo_tool.description is not None

            # Verify the echo tool has the expected input schema
            assert hasattr(echo_tool, "inputSchema")
            assert echo_tool.inputSchema is not None

        finally:
            # Clean up the connection
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_run_echo_tool(self, stdio_client):
        """Test running the echo tool from the Everything server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Find the echo tool
            echo_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "echo":
                    echo_tool = tool
                    break

            assert echo_tool is not None, "Echo tool not found"

            # Run the echo tool
            test_message = "Hello, MCP!"
            result = await stdio_client.run_tool("echo", {"message": test_message})

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

            # Check that the echo worked - content should contain our message
            content_text = str(result.content[0])
            assert test_message in content_text or "Echo:" in content_text

        finally:
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_list_all_tools(self, stdio_client):
        """Test listing all available tools from the Everything server."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Connect to the server
            tools = await stdio_client.connect_to_server(command)

            # Verify we have multiple tools
            assert len(tools) >= 3  # Everything server typically has several tools

            # Check that tools have the expected attributes
            for tool in tools:
                assert hasattr(tool, "name")
                assert hasattr(tool, "description")
                assert hasattr(tool, "inputSchema")
                assert tool.name is not None
                assert len(tool.name) > 0

            # Common tools that should be available
            expected_tools = ["echo"]  # Echo is typically available
            for expected_tool in expected_tools:
                assert any(tool.name == expected_tool for tool in tools), f"Expected tool '{expected_tool}' not found"

        finally:
            await stdio_client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_session_reuse(self, stdio_client):
        """Test that sessions are properly reused."""
        command = "npx -y @modelcontextprotocol/server-everything"

        try:
            # Set session context
            stdio_client.set_session_context("test_session_reuse")

            # Connect to the server
            tools1 = await stdio_client.connect_to_server(command)

            # Connect again - should reuse the session
            tools2 = await stdio_client.connect_to_server(command)

            # Should have the same tools
            assert len(tools1) == len(tools2)

            # Run a tool to verify the session is working
            result = await stdio_client.run_tool("echo", {"message": "Session reuse test"})
            assert result is not None

        finally:
            await stdio_client.disconnect()


class TestMCPStreamableHttpClientWithDeepWikiServer:
    """Test MCPSseClient with the DeepWiki MCP server."""

    @pytest.fixture
    def streamable_http_client(self):
        """Create an SSE client for testing."""
        return MCPStreamableHttpClient()

    @pytest.mark.asyncio
    async def test_connect_to_deepwiki_server(self, streamable_http_client):
        """Test connecting to the DeepWiki MCP server."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await streamable_http_client.connect_to_server(url)

            # Verify tools were returned
            assert len(tools) > 0

            # Check for expected DeepWiki tools
            expected_tools = ["read_wiki_structure", "read_wiki_contents", "ask_question"]

            # Verify we have the expected tools
            for expected_tool in expected_tools:
                assert any(tool.name == expected_tool for tool in tools), f"Expected tool '{expected_tool}' not found"

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")
        finally:
            await streamable_http_client.disconnect()

    @pytest.mark.asyncio
    async def test_run_wiki_structure_tool(self, streamable_http_client):
        """Test running the read_wiki_structure tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await streamable_http_client.connect_to_server(url)

            # Find the read_wiki_structure tool
            wiki_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "read_wiki_structure":
                    wiki_tool = tool
                    break

            assert wiki_tool is not None, "read_wiki_structure tool not found"

            # Run the tool with a test repository (use repoName as expected by the API)
            result = await streamable_http_client.run_tool("read_wiki_structure", {"repoName": "microsoft/vscode"})

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await streamable_http_client.disconnect()

    @pytest.mark.asyncio
    async def test_ask_question_tool(self, streamable_http_client):
        """Test running the ask_question tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await streamable_http_client.connect_to_server(url)

            # Find the ask_question tool
            ask_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "ask_question":
                    ask_tool = tool
                    break

            assert ask_tool is not None, "ask_question tool not found"

            # Run the tool with a test question (use repoName as expected by the API)
            result = await streamable_http_client.run_tool(
                "ask_question", {"repoName": "microsoft/vscode", "question": "What is VS Code?"}
            )

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await streamable_http_client.disconnect()

    @pytest.mark.asyncio
    async def test_url_validation(self, streamable_http_client):
        """Test URL validation for SSE connections."""
        # Test valid URL
        valid_url = "https://mcp.deepwiki.com/sse"
        is_valid, error = await streamable_http_client.validate_url(valid_url)
        # Either valid or accessible, or rate-limited (429) which indicates server is reachable
        if not is_valid and "429" in error:
            # Rate limiting indicates the server is accessible but limiting requests
            # This is a transient network issue, not a test failure
            pytest.skip(f"DeepWiki server is rate limiting requests: {error}")
        assert is_valid or error == ""  # Either valid or accessible

        # Test invalid URL
        invalid_url = "not_a_url"
        is_valid, error = await streamable_http_client.validate_url(invalid_url)
        assert not is_valid
        assert error != ""

    @pytest.fixture
    def mock_tool(self):
        """Create a mock MCP tool."""
        tool = MagicMock()
        tool.name = "test_tool"
        tool.description = "Test tool description"
        tool.inputSchema = {
            "type": "object",
            "properties": {"test_param": {"type": "string", "description": "Test parameter"}},
            "required": ["test_param"],
        }
        return tool

    @pytest.fixture
    def mock_session(self, mock_tool):
        """Create a mock ClientSession."""
        session = AsyncMock()
        session.initialize = AsyncMock()
        list_tools_result = MagicMock()
        list_tools_result.tools = [mock_tool]
        session.list_tools = AsyncMock(return_value=list_tools_result)
        session.call_tool = AsyncMock(
            return_value=MagicMock(content=[MagicMock(model_dump=lambda: {"result": "success"})])
        )
        return session


class TestMCPSseClientUnit:
    """Unit tests for MCPSseClient functionality."""

    @pytest.fixture
    def sse_client(self):
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_client_initialization(self, sse_client):
        """Test that SSE client initializes correctly."""
        # Client should initialize with default values
        assert sse_client.session is None
        assert sse_client._connection_params is None
        assert sse_client._connected is False
        assert sse_client._session_context is None

    async def test_validate_url_valid(self, sse_client):
        """Test URL validation with valid URL."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            is_valid, error_msg = await sse_client.validate_url("http://test.url")

            assert is_valid is True
            assert error_msg == ""

    async def test_validate_url_invalid_format(self, sse_client):
        """Test URL validation with invalid format."""
        is_valid, error_msg = await sse_client.validate_url("invalid-url")

        assert is_valid is False
        assert "Invalid URL format" in error_msg

    async def test_validate_url_with_404_response(self, sse_client):
        """Test URL validation with 404 response (should be valid for SSE)."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            is_valid, error_msg = await sse_client.validate_url("http://test.url")

            assert is_valid is True
            assert error_msg == ""

    async def test_connect_to_server_with_headers(self, sse_client):
        """Test connecting to server via SSE with custom headers."""
        test_url = "http://test.url"
        test_headers = {"Authorization": "Bearer token123", "Custom-Header": "value"}
        expected_headers = {"authorization": "Bearer token123", "custom-header": "value"}  # normalized

        with (
            patch.object(sse_client, "validate_url", return_value=(True, "")),
            patch.object(sse_client, "_get_or_create_session") as mock_get_session,
        ):
            # Mock session
            mock_session = AsyncMock()
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            list_tools_result = MagicMock()
            list_tools_result.tools = [mock_tool]
            mock_session.list_tools = AsyncMock(return_value=list_tools_result)
            mock_get_session.return_value = mock_session

            tools = await sse_client.connect_to_server(test_url, test_headers)

            assert len(tools) == 1
            assert tools[0].name == "test_tool"
            assert sse_client._connected is True

            # Verify headers are stored in connection params (normalized)
            assert sse_client._connection_params is not None
            assert sse_client._connection_params["headers"] == expected_headers
            assert sse_client._connection_params["url"] == test_url

    async def test_headers_passed_to_session_manager(self, sse_client):
        """Test that headers are properly passed to the session manager."""
        test_url = "http://test.url"
        expected_headers = {"authorization": "Bearer token123", "x-api-key": "secret"}  # normalized

        sse_client._session_context = "test_context"
        sse_client._connection_params = {
            "url": test_url,
            "headers": expected_headers,  # Use normalized headers
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
        }

        with patch.object(sse_client, "_get_session_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_session = AsyncMock()
            mock_manager.get_session = AsyncMock(return_value=mock_session)
            mock_get_manager.return_value = mock_manager

            result_session = await sse_client._get_or_create_session()

            # Verify session manager was called with correct parameters including normalized headers
            mock_manager.get_session.assert_called_once_with(
                "test_context", sse_client._connection_params, "streamable_http"
            )
            assert result_session == mock_session

    async def test_run_tool_with_retry_on_connection_error(self, sse_client):
        """Test that run_tool retries on connection errors."""
        # Setup connection state
        sse_client._connected = True
        sse_client._connection_params = {"url": "http://test.url", "headers": {}}
        sse_client._session_context = "test_context"

        call_count = 0

        async def mock_get_session_side_effect():
            nonlocal call_count
            call_count += 1
            session = AsyncMock()
            if call_count == 1:
                # First call fails with connection error
                from anyio import ClosedResourceError

                session.call_tool = AsyncMock(side_effect=ClosedResourceError())
            else:
                # Second call succeeds
                mock_result = MagicMock()
                session.call_tool = AsyncMock(return_value=mock_result)
            return session

        with (
            patch.object(sse_client, "_get_or_create_session", side_effect=mock_get_session_side_effect),
            patch.object(sse_client, "_get_session_manager") as mock_get_manager,
        ):
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            result = await sse_client.run_tool("test_tool", {"param": "value"})

            # Should have retried and succeeded on second attempt
            assert call_count == 2
            assert result is not None
            # Should have cleaned up the failed session
            mock_manager._cleanup_session.assert_called_once_with("test_context")


class TestMCPStructuredTool:
    """Test the MCPStructuredTool inner methods."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock MCP client."""
        from unittest.mock import AsyncMock

        client = AsyncMock()
        client.run_tool = AsyncMock(return_value="tool_result")
        return client

    @pytest.fixture
    def test_schema(self):
        """Create a test Pydantic schema with snake_case fields."""
        from pydantic import Field, create_model

        return create_model(
            "TestSchema",
            weather_main=(str, Field(..., description="Main weather condition")),
            top_n=(int, Field(..., description="Number of results")),
            user_id=(str, Field(default="default_user", description="User identifier")),
        )

    @pytest.fixture
    def mcp_tool(self, test_schema, mock_client):
        """Create an MCPStructuredTool instance for testing."""
        import json

        # Import the MCPStructuredTool class from the actual code
        # We need to recreate it here since it's defined inline in the update_tools function
        from langchain_core.tools import StructuredTool
        from lfx.base.mcp.util import create_tool_coroutine, create_tool_func

        class MCPStructuredTool(StructuredTool):
            def run(self, tool_input: str | dict, config=None, **kwargs):
                """Override the main run method to handle parameter conversion before validation."""
                # Parse tool_input if it's a string
                if isinstance(tool_input, str):
                    try:
                        parsed_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        parsed_input = {"input": tool_input}
                else:
                    parsed_input = tool_input or {}

                # Convert camelCase parameters to snake_case
                converted_input = self._convert_parameters(parsed_input)

                # Call the parent run method with converted parameters
                return super().run(converted_input, config=config, **kwargs)

            async def arun(self, tool_input: str | dict, config=None, **kwargs):
                """Override the main arun method to handle parameter conversion before validation."""
                # Parse tool_input if it's a string
                if isinstance(tool_input, str):
                    try:
                        parsed_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        parsed_input = {"input": tool_input}
                else:
                    parsed_input = tool_input or {}

                # Convert camelCase parameters to snake_case
                converted_input = self._convert_parameters(parsed_input)

                # Call the parent arun method with converted parameters
                return await super().arun(converted_input, config=config, **kwargs)

            def _convert_parameters(self, input_dict):
                if not input_dict or not isinstance(input_dict, dict):
                    return input_dict

                from lfx.base.mcp.util import _camel_to_snake

                converted_dict = {}
                original_fields = set(self.args_schema.model_fields.keys())

                for key, value in input_dict.items():
                    if key in original_fields:
                        # Field exists as-is
                        converted_dict[key] = value
                    else:
                        # Try to convert camelCase to snake_case
                        snake_key = _camel_to_snake(key)
                        if snake_key in original_fields:
                            converted_dict[snake_key] = value
                        else:
                            # Keep original key
                            converted_dict[key] = value

                return converted_dict

        return MCPStructuredTool(
            name="test_tool",
            description="Test tool for unit testing",
            args_schema=test_schema,
            func=create_tool_func("test_tool", test_schema, mock_client),
            coroutine=create_tool_coroutine("test_tool", test_schema, mock_client),
        )

    def test_convert_parameters_exact_match(self, mcp_tool):
        """Test _convert_parameters with fields that exactly match schema."""
        input_dict = {"weather_main": "Snow", "top_n": 5, "user_id": "user123"}

        result = mcp_tool._convert_parameters(input_dict)

        # Should pass through unchanged since fields match exactly
        assert result == {"weather_main": "Snow", "top_n": 5, "user_id": "user123"}

    def test_convert_parameters_camel_to_snake(self, mcp_tool):
        """Test _convert_parameters converts camelCase to snake_case."""
        input_dict = {"weatherMain": "Rain", "topN": 10, "userId": "user456"}

        result = mcp_tool._convert_parameters(input_dict)

        # Should convert camelCase to snake_case
        assert result == {"weather_main": "Rain", "top_n": 10, "user_id": "user456"}

    def test_convert_parameters_mixed_fields(self, mcp_tool):
        """Test _convert_parameters with mixed exact and camelCase fields."""
        input_dict = {
            "weather_main": "Cloudy",  # Exact match
            "topN": 3,  # CamelCase -> snake_case
            "userId": "user789",  # CamelCase -> snake_case
        }

        result = mcp_tool._convert_parameters(input_dict)

        assert result == {"weather_main": "Cloudy", "top_n": 3, "user_id": "user789"}

    def test_convert_parameters_unknown_fields(self, mcp_tool):
        """Test _convert_parameters with fields not in schema."""
        input_dict = {"weatherMain": "Sunny", "unknownField": "value", "anotherUnknown": 42}

        result = mcp_tool._convert_parameters(input_dict)

        # Known fields should be converted, unknown fields kept as-is
        assert result == {"weather_main": "Sunny", "unknownField": "value", "anotherUnknown": 42}

    def test_convert_parameters_empty_input(self, mcp_tool):
        """Test _convert_parameters with empty/None input."""
        assert mcp_tool._convert_parameters({}) == {}
        assert mcp_tool._convert_parameters(None) is None
        assert mcp_tool._convert_parameters("not_a_dict") == "not_a_dict"

    def test_convert_parameters_preserves_value_types(self, mcp_tool):
        """Test _convert_parameters preserves all value types correctly."""
        input_dict = {
            "weatherMain": "Snow",
            "topN": 42,
            "complexData": {"nested": "value", "list": [1, 2, 3], "boolean": True},
        }

        result = mcp_tool._convert_parameters(input_dict)

        expected = {
            "weather_main": "Snow",
            "top_n": 42,
            "complexData": {"nested": "value", "list": [1, 2, 3], "boolean": True},
        }
        assert result == expected

    def test_run_with_dict_input(self, mcp_tool, mock_client):
        """Test run method with dictionary input."""
        # Test with all required fields
        input_data = {"weatherMain": "Snow", "topN": 5}

        mcp_tool.run(input_data)

        # Verify the mock client was called with converted parameters
        mock_client.run_tool.assert_called_once()
        call_args = mock_client.run_tool.call_args[1]["arguments"]
        assert call_args["weather_main"] == "Snow"
        assert call_args["top_n"] == 5

    def test_run_with_string_input_json(self, mcp_tool, mock_client):
        """Test run method with valid JSON string input."""
        import json

        input_data = json.dumps({"weatherMain": "Rain", "topN": 3})

        mcp_tool.run(input_data)

        # Verify the mock client was called with converted parameters
        mock_client.run_tool.assert_called_once()
        call_args = mock_client.run_tool.call_args[1]["arguments"]
        assert call_args["weather_main"] == "Rain"
        assert call_args["top_n"] == 3

    def test_run_with_string_input_non_json(self, mcp_tool):
        """Test run method with non-JSON string input."""
        # This will cause a validation error since we have required fields
        # Let's test that the error handling works
        with pytest.raises(Exception):  # noqa: B017, PT011
            mcp_tool.run("simple string input")

    def test_run_with_none_input(self, mcp_tool):
        """Test run method with None input."""
        # This will cause a validation error since we have required fields
        with pytest.raises(Exception):  # noqa: B017, PT011
            mcp_tool.run(None)

    @pytest.mark.asyncio
    async def test_arun_with_dict_input(self, mcp_tool, mock_client):
        """Test arun method with dictionary input."""
        input_data = {"weatherMain": "Snow", "topN": 8}

        await mcp_tool.arun(input_data)

        # Verify the mock client was called with converted parameters
        mock_client.run_tool.assert_called_once()
        call_args = mock_client.run_tool.call_args[1]["arguments"]
        assert call_args["weather_main"] == "Snow"
        assert call_args["top_n"] == 8

    @pytest.mark.asyncio
    async def test_arun_with_string_input_json(self, mcp_tool, mock_client):
        """Test arun method with valid JSON string input."""
        import json

        input_data = json.dumps({"weatherMain": "Storm", "topN": 1})

        await mcp_tool.arun(input_data)

        # Verify the mock client was called with converted parameters
        mock_client.run_tool.assert_called_once()
        call_args = mock_client.run_tool.call_args[1]["arguments"]
        assert call_args["weather_main"] == "Storm"
        assert call_args["top_n"] == 1

    @pytest.mark.asyncio
    async def test_arun_with_string_input_non_json(self, mcp_tool):
        """Test arun method with non-JSON string input."""
        # This will cause a validation error since we have required fields
        with pytest.raises(Exception):  # noqa: B017, PT011
            await mcp_tool.arun("async string input")

    @pytest.mark.asyncio
    async def test_arun_with_none_input(self, mcp_tool):
        """Test arun method with None input."""
        # This will cause a validation error since we have required fields
        with pytest.raises(Exception):  # noqa: B017, PT011
            await mcp_tool.arun(None)

    def test_run_passes_config_and_kwargs(self, mcp_tool, mock_client):
        """Test that run method properly passes config and kwargs to parent."""
        from unittest.mock import MagicMock, patch

        input_data = {"weatherMain": "Clear", "topN": 1}
        config = {"some": "config"}
        extra_kwargs = {"extra": "param"}

        # Mock the event loop to prevent the "no current event loop" error
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(return_value="tool_result")

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Just verify that the method completes successfully with config/kwargs
            mcp_tool.run(input_data, config=config, **extra_kwargs)

            # Verify the tool was executed
            mock_client.run_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_arun_passes_config_and_kwargs(self, mcp_tool, mock_client):
        """Test that arun method properly passes config and kwargs to parent."""
        input_data = {"weatherMain": "Hail", "topN": 2}
        config = {"async": "config"}
        extra_kwargs = {"async_extra": "param"}

        # Just verify that the method completes successfully with config/kwargs
        await mcp_tool.arun(input_data, config=config, **extra_kwargs)

        # Verify the tool was executed
        mock_client.run_tool.assert_called_once()

    def test_run_integration_with_validation_error(self, mcp_tool):
        """Test run method handles validation errors properly."""
        # Input missing required field to trigger validation error
        input_data = {"weatherMain": "Snow"}  # Missing topN

        with pytest.raises(Exception):  # noqa: B017, PT011
            mcp_tool.run(input_data)

    @pytest.mark.asyncio
    async def test_arun_integration_with_validation_error(self, mcp_tool):
        """Test arun method handles validation errors properly."""
        # Input missing required field to trigger validation error
        input_data = {"weatherMain": "Rain"}  # Missing topN

        with pytest.raises(Exception):  # noqa: B017, PT011
            await mcp_tool.arun(input_data)


class TestSnakeToCamelConversion:
    """Test the _snake_to_camel function from json_schema module."""

    def test_snake_to_camel_basic(self):
        """Test basic snake_case to camelCase conversion."""
        from lfx.schema.json_schema import _snake_to_camel

        assert _snake_to_camel("weather_main") == "weatherMain"
        assert _snake_to_camel("top_n") == "topN"
        assert _snake_to_camel("first_name") == "firstName"
        assert _snake_to_camel("last_name") == "lastName"
        assert _snake_to_camel("user_id") == "userId"

    def test_snake_to_camel_single_word(self):
        """Test single word conversion (should remain unchanged)."""
        from lfx.schema.json_schema import _snake_to_camel

        assert _snake_to_camel("simple") == "simple"
        assert _snake_to_camel("name") == "name"
        assert _snake_to_camel("id") == "id"

    def test_snake_to_camel_empty_string(self):
        """Test empty string handling."""
        from lfx.schema.json_schema import _snake_to_camel

        assert _snake_to_camel("") == ""

    def test_snake_to_camel_leading_underscores(self):
        """Test that leading underscores are preserved."""
        from lfx.schema.json_schema import _snake_to_camel

        # Single leading underscore (private convention)
        assert _snake_to_camel("_my_variable") == "_myVariable"
        assert _snake_to_camel("_user_id") == "_userId"
        assert _snake_to_camel("_internal_name") == "_internalName"

        # Double leading underscore (strongly private convention)
        assert _snake_to_camel("__private_var") == "__privateVar"
        assert _snake_to_camel("__init_method") == "__initMethod"

        # Dunder methods (magic methods)
        assert _snake_to_camel("__special_method__") == "__specialMethod__"

    def test_snake_to_camel_trailing_underscores(self):
        """Test that trailing underscores are preserved."""
        from lfx.schema.json_schema import _snake_to_camel

        # Single trailing underscore (keyword conflict avoidance)
        assert _snake_to_camel("class_") == "class_"
        assert _snake_to_camel("type_") == "type_"
        assert _snake_to_camel("from_address_") == "fromAddress_"

        # Multiple trailing underscores
        assert _snake_to_camel("reserved_word__") == "reservedWord__"

    def test_snake_to_camel_both_leading_and_trailing(self):
        """Test preservation of both leading and trailing underscores."""
        from lfx.schema.json_schema import _snake_to_camel

        assert _snake_to_camel("_my_class_") == "_myClass_"
        assert _snake_to_camel("__private_type__") == "__privateType__"
        assert _snake_to_camel("_internal_method_") == "_internalMethod_"

    def test_snake_to_camel_only_underscores(self):
        """Test strings that are only underscores."""
        from lfx.schema.json_schema import _snake_to_camel

        assert _snake_to_camel("_") == "_"
        assert _snake_to_camel("__") == "__"
        assert _snake_to_camel("___") == "___"

    def test_snake_to_camel_multiple_consecutive_underscores(self):
        """Test handling of multiple consecutive underscores in the middle."""
        from lfx.schema.json_schema import _snake_to_camel

        # Multiple underscores should be treated as separators
        # Note: This tests current behavior - we may want to normalize this
        assert _snake_to_camel("my__double__underscore") == "myDoubleUnderscore"
        assert _snake_to_camel("triple___underscore") == "tripleUnderscore"

    def test_snake_to_camel_edge_cases(self):
        """Test various edge cases."""
        from lfx.schema.json_schema import _snake_to_camel

        # Single character components
        assert _snake_to_camel("a_b_c") == "aBC"

        # Numbers in names
        assert _snake_to_camel("version_2_beta") == "version2Beta"
        assert _snake_to_camel("test_123_value") == "test123Value"

        # Already camelCase (no underscores)
        assert _snake_to_camel("alreadyCamelCase") == "alreadyCamelCase"

    def test_snake_to_camel_with_api_field_names(self):
        """Test conversion of common API field names that should preserve underscores."""
        from lfx.schema.json_schema import _snake_to_camel

        # MongoDB-style IDs
        assert _snake_to_camel("_id") == "_id"

        # Type discriminators
        assert _snake_to_camel("_type") == "_type"

        # Metadata fields
        assert _snake_to_camel("_meta_data") == "_metaData"
        assert _snake_to_camel("_created_at") == "_createdAt"
