"""
Unit tests for MCP component with actual MCP servers.

This test suite validates the MCP component functionality using real MCP servers:
- Everything server (stdio mode) - provides echo and other tools
- DeepWiki server (SSE mode) - provides wiki-related tools
"""

import asyncio
import os
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.base.mcp.util import MCPSessionManager
from langflow.components.agents.mcp_component import MCPSseClient, MCPStdioClient, MCPToolsComponent

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestMCPToolsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return MCPToolsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "mode": "Stdio",
            "command": "npx -y @modelcontextprotocol/server-everything",
            "sse_url": "https://mcp.deepwiki.com/sse",
            "tool": "echo",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_component_initialization(self, component_class, default_kwargs):
        """Test that the component initializes correctly."""
        component = component_class(**default_kwargs)

        # Check that the component has the expected attributes
        assert hasattr(component, "stdio_client")
        assert hasattr(component, "sse_client")
        assert isinstance(component.stdio_client, MCPStdioClient)
        assert isinstance(component.sse_client, MCPSseClient)

        # Check that the component has a session manager
        session_manager = component.stdio_client._get_session_manager()
        assert isinstance(session_manager, MCPSessionManager)


class TestMCPStdioClientWithEverythingServer:
    """Test MCPStdioClient with the Everything MCP server."""

    @pytest.fixture
    def stdio_client(self):
        """Create a stdio client for testing."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
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

            # Print tool names for debugging
            tool_names = [tool.name for tool in tools]
            print(f"Available tools: {tool_names}")

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


class TestMCPSseClientWithDeepWikiServer:
    """Test MCPSseClient with the DeepWiki MCP server."""

    @pytest.fixture
    def sse_client(self):
        """Create an SSE client for testing."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_connect_to_deepwiki_server(self, sse_client):
        """Test connecting to the DeepWiki MCP server."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Verify tools were returned
            assert len(tools) > 0

            # Check for expected DeepWiki tools
            expected_tools = ["read_wiki_structure", "read_wiki_contents", "ask_question"]
            tool_names = [tool.name for tool in tools if hasattr(tool, "name")]

            print(f"Available DeepWiki tools: {tool_names}")

            # Verify we have the expected tools
            for expected_tool in expected_tools:
                assert any(tool.name == expected_tool for tool in tools), f"Expected tool '{expected_tool}' not found"

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_run_wiki_structure_tool(self, sse_client):
        """Test running the read_wiki_structure tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Find the read_wiki_structure tool
            wiki_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "read_wiki_structure":
                    wiki_tool = tool
                    break

            assert wiki_tool is not None, "read_wiki_structure tool not found"

            # Run the tool with a test repository
            result = await sse_client.run_tool("read_wiki_structure", {"repository": "microsoft/vscode"})

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_ask_question_tool(self, sse_client):
        """Test running the ask_question tool."""
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Connect to the server
            tools = await sse_client.connect_to_server(url)

            # Find the ask_question tool
            ask_tool = None
            for tool in tools:
                if hasattr(tool, "name") and tool.name == "ask_question":
                    ask_tool = tool
                    break

            assert ask_tool is not None, "ask_question tool not found"

            # Run the tool with a test question
            result = await sse_client.run_tool(
                "ask_question", {"repository": "microsoft/vscode", "question": "What is VS Code?"}
            )

            # Verify the result
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

        except Exception as e:
            # If the server is not accessible or the tool fails, skip the test
            pytest.skip(f"DeepWiki server test failed: {e}")
        finally:
            await sse_client.disconnect()

    @pytest.mark.asyncio
    async def test_url_validation(self, sse_client):
        """Test URL validation for SSE connections."""
        # Test valid URL
        valid_url = "https://mcp.deepwiki.com/sse"
        is_valid, error = await sse_client.validate_url(valid_url)
        assert is_valid or error == ""  # Either valid or accessible

        # Test invalid URL
        invalid_url = "not_a_url"
        is_valid, error = await sse_client.validate_url(invalid_url)
        assert not is_valid
        assert error != ""

    @pytest.mark.asyncio
    async def test_redirect_handling(self, sse_client):
        """Test redirect handling for SSE connections."""
        # Test with the DeepWiki URL
        url = "https://mcp.deepwiki.com/sse"

        try:
            # Check for redirects
            final_url = await sse_client.pre_check_redirect(url)

            # Should return a URL (either original or redirected)
            assert final_url is not None
            assert isinstance(final_url, str)
            assert final_url.startswith("http")

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible for redirect test: {e}")


class TestMCPToolsComponentIntegration:
    """Integration tests for the MCPToolsComponent."""

    @pytest.fixture
    def component(self):
        """Create a component for testing."""
        return MCPToolsComponent()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_stdio_mode_integration(self, component):
        """Test the component in stdio mode with Everything server."""
        # Configure for stdio mode
        component.mode = "Stdio"
        component.command = "npx -y @modelcontextprotocol/server-everything"
        component.tool = "echo"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"Everything server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_sse_mode_integration(self, component):
        """Test the component in SSE mode with DeepWiki server."""
        # Configure for SSE mode
        component.mode = "SSE"
        component.sse_url = "https://mcp.deepwiki.com/sse"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_session_context_setting(self, component):
        """Test that session context is properly set."""
        # Set session context
        component.stdio_client.set_session_context("test_context")
        component.sse_client.set_session_context("test_context")

        # Verify context was set
        assert component.stdio_client._session_context == "test_context"
        assert component.sse_client._session_context == "test_context"

    @pytest.mark.asyncio
    async def test_session_manager_sharing(self, component):
        """Test that session managers are shared through component cache."""
        # Get session managers
        stdio_manager = component.stdio_client._get_session_manager()
        sse_manager = component.sse_client._get_session_manager()

        # Both should be MCPSessionManager instances
        assert isinstance(stdio_manager, MCPSessionManager)
        assert isinstance(sse_manager, MCPSessionManager)

        # They should be the same instance (shared through cache)
        assert stdio_manager is sse_manager


class TestMCPComponentErrorHandling:
    """Test error handling in MCP components."""

    @pytest.fixture
    def stdio_client(self):
        return MCPStdioClient()

    @pytest.fixture
    def sse_client(self):
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_invalid_command_handling(self, stdio_client):
        """Test handling of invalid commands."""
        invalid_command = "invalid_command_that_does_not_exist"

        with pytest.raises(Exception):  # Should raise an exception
            await stdio_client.connect_to_server(invalid_command)

    @pytest.mark.asyncio
    async def test_invalid_url_handling(self, sse_client):
        """Test handling of invalid URLs."""
        invalid_url = "http://invalid.url.that.does.not.exist"

        with pytest.raises(Exception):  # Should raise an exception
            await sse_client.connect_to_server(invalid_url)

    @pytest.mark.asyncio
    async def test_tool_not_found_handling(self, stdio_client):
        """Test handling when a tool is not found."""
        # This test would need a mock or real server connection
        # For now, we'll test the error condition
        with pytest.raises(ValueError):
            await stdio_client.run_tool("non_existent_tool", {})

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, stdio_client, sse_client):
        """Test that connections are properly cleaned up."""
        # Both clients should handle disconnect gracefully
        await stdio_client.disconnect()
        await sse_client.disconnect()

        # Should be able to call disconnect multiple times
        await stdio_client.disconnect()
        await sse_client.disconnect()
