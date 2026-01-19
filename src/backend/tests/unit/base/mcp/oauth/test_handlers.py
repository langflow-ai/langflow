"""Unit tests for MCP OAuth handlers.

This test suite validates the OAuth callback handler functionality including:
- OAuthCallbackHandler: Local HTTP server for OAuth callbacks
- Helper functions for redirect and callback handling
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from lfx.base.mcp.oauth.handlers import (
    OAuthCallbackHandler,
    create_callback_handler,
    create_redirect_handler,
)


class TestOAuthCallbackHandler:
    """Tests for OAuthCallbackHandler class."""

    @pytest.fixture
    def handler(self) -> OAuthCallbackHandler:
        """Create an OAuthCallbackHandler instance."""
        return OAuthCallbackHandler()

    @pytest.fixture
    def handler_with_port(self) -> OAuthCallbackHandler:
        """Create an OAuthCallbackHandler with a specific port."""
        return OAuthCallbackHandler(port=0)  # 0 = auto-assign

    @pytest.mark.asyncio
    async def test_start_returns_redirect_uri(self, handler: OAuthCallbackHandler) -> None:
        """Test that start() returns a valid redirect URI."""
        try:
            redirect_uri = await handler.start()

            assert redirect_uri.startswith("http://127.0.0.1:")
            assert "/callback" in redirect_uri
        finally:
            handler.shutdown()

    @pytest.mark.asyncio
    async def test_start_assigns_port(self, handler: OAuthCallbackHandler) -> None:
        """Test that start() assigns a valid port."""
        try:
            redirect_uri = await handler.start()

            # Extract port from URI
            port_str = redirect_uri.split(":")[2].split("/")[0]
            port = int(port_str)

            assert port > 0
            assert port < 65536
        finally:
            handler.shutdown()

    @pytest.mark.asyncio
    async def test_wait_for_callback_times_out(self, handler: OAuthCallbackHandler) -> None:
        """Test that wait_for_callback times out when no callback is received."""
        await handler.start()

        try:
            with pytest.raises(TimeoutError, match="timed out"):
                await handler.wait_for_callback(timeout=0.1)
        finally:
            handler.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_server(self, handler: OAuthCallbackHandler) -> None:
        """Test that shutdown() cleans up the server."""
        await handler.start()
        assert handler._server is not None

        handler.shutdown()
        assert handler._server is None

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self, handler: OAuthCallbackHandler) -> None:
        """Test that shutdown() can be called multiple times safely."""
        await handler.start()
        handler.shutdown()
        handler.shutdown()  # Should not raise

    def test_initial_state(self, handler: OAuthCallbackHandler) -> None:
        """Test that handler starts in clean state."""
        assert handler._auth_code is None
        assert handler._state is None
        assert handler._error is None
        assert handler._server is None


class TestCallbackHandlerWithSimulatedCallback:
    """Tests for callback handling with simulated OAuth responses."""

    @pytest.mark.asyncio
    async def test_callback_with_auth_code(self) -> None:
        """Test handling a successful OAuth callback with authorization code."""
        handler = OAuthCallbackHandler()

        try:
            await handler.start()

            # Simulate receiving a callback
            handler._auth_code = "test_auth_code"
            handler._state = "test_state"
            handler._received.set()

            auth_code, state = await handler.wait_for_callback(timeout=1.0)

            assert auth_code == "test_auth_code"
            assert state == "test_state"
        finally:
            handler.shutdown()

    @pytest.mark.asyncio
    async def test_callback_with_error(self) -> None:
        """Test handling an OAuth error callback."""
        handler = OAuthCallbackHandler()

        try:
            await handler.start()

            # Simulate receiving an error callback
            handler._error = "access_denied"
            handler._error_description = "User denied access"
            handler._received.set()

            with pytest.raises(ValueError, match="OAuth error"):
                await handler.wait_for_callback(timeout=1.0)
        finally:
            handler.shutdown()

    @pytest.mark.asyncio
    async def test_callback_without_code(self) -> None:
        """Test handling a callback without authorization code."""
        handler = OAuthCallbackHandler()

        try:
            await handler.start()

            # Simulate receiving callback without code
            handler._auth_code = None
            handler._received.set()

            with pytest.raises(ValueError, match="No authorization code"):
                await handler.wait_for_callback(timeout=1.0)
        finally:
            handler.shutdown()


class TestCreateRedirectHandler:
    """Tests for create_redirect_handler function."""

    @pytest.mark.asyncio
    async def test_creates_redirect_handler(self) -> None:
        """Test that create_redirect_handler returns a callable."""
        redirect_handler = await create_redirect_handler()

        assert callable(redirect_handler)

    @pytest.mark.asyncio
    async def test_redirect_handler_opens_browser(self) -> None:
        """Test that redirect handler opens browser with URL."""
        redirect_handler = await create_redirect_handler()

        with patch("webbrowser.open") as mock_open:
            await redirect_handler("https://example.com/oauth/authorize")

            mock_open.assert_called_once_with("https://example.com/oauth/authorize")


class TestCreateCallbackHandler:
    """Tests for create_callback_handler function."""

    @pytest.mark.asyncio
    async def test_creates_callback_infrastructure(self) -> None:
        """Test that create_callback_handler sets up callback infrastructure."""
        callback_fn, redirect_uri, cleanup = await create_callback_handler()

        try:
            assert callable(callback_fn)
            assert callable(cleanup)
            assert redirect_uri.startswith("http://127.0.0.1:")
            assert "/callback" in redirect_uri
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_function_works(self) -> None:
        """Test that cleanup function properly cleans up resources."""
        _, _, cleanup = await create_callback_handler()

        # Should not raise
        cleanup()
        cleanup()  # Idempotent

    @pytest.mark.asyncio
    async def test_custom_port_and_timeout(self) -> None:
        """Test that custom port and timeout are accepted."""
        _callback_fn, redirect_uri, cleanup = await create_callback_handler(
            port=0,
            timeout=60.0,
        )

        try:
            assert redirect_uri.startswith("http://127.0.0.1:")
        finally:
            cleanup()
