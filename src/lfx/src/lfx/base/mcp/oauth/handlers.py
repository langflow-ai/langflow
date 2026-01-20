"""OAuth callback handlers for MCP authentication.

This module provides the redirect and callback handlers required by
the MCP SDK's OAuthClientProvider:
- OAuthCallbackHandler: Manages a local HTTP server to receive OAuth callbacks
- Helper functions to create redirect and callback handlers
"""

from __future__ import annotations

import asyncio
import contextlib
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


class OAuthCallbackHandler:
    """Manages OAuth callback reception via a local HTTP server.

    This class creates a temporary local HTTP server to receive the OAuth
    authorization callback. The server runs in a background thread and
    captures the authorization code and state from the callback URL.

    Usage:
        handler = OAuthCallbackHandler()
        redirect_uri = await handler.start()
        # ... trigger OAuth flow with redirect_uri ...
        auth_code, state = await handler.wait_for_callback()
        handler.shutdown()
    """

    def __init__(self, port: int = 18085, host: str = "localhost") -> None:
        """Initialize the callback handler.

        Args:
            port: The port to listen on. Default is 18085 (less common port to avoid conflicts).
            host: The host to bind to and use in redirect_uri. Default is "localhost"
                for OAuth provider compatibility (some reject "127.0.0.1").
        """
        self._port = port
        self._host = host
        self._auth_code: str | None = None
        self._state: str | None = None
        self._error: str | None = None
        self._error_description: str | None = None
        self._server: HTTPServer | None = None
        self._received = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> str:
        """Start the callback server.

        Creates and starts a local HTTP server in a background thread
        to listen for the OAuth callback.

        Returns:
            The redirect URI to use in the OAuth authorization request.
        """
        self._loop = asyncio.get_event_loop()
        handler = self

        class CallbackRequestHandler(BaseHTTPRequestHandler):
            """HTTP request handler for OAuth callbacks."""

            def do_GET(self) -> None:
                """Handle GET requests containing OAuth callback parameters."""
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Extract OAuth parameters (accessing outer handler's state is intentional)
                handler._auth_code = params.get("code", [None])[0]  # noqa: SLF001
                handler._state = params.get("state", [None])[0]  # noqa: SLF001
                handler._error = params.get("error", [None])[0]  # noqa: SLF001
                handler._error_description = params.get("error_description", [None])[0]  # noqa: SLF001

                # Send response to user's browser
                if handler._error:  # noqa: SLF001
                    self._send_error_response()
                else:
                    self._send_success_response()

                # Signal that we received the callback
                if handler._loop is not None:  # noqa: SLF001
                    handler._loop.call_soon_threadsafe(handler._received.set)  # noqa: SLF001

            def _send_success_response(self) -> None:
                """Send a success response to the browser."""
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                html = b"""<!DOCTYPE html>
<html>
<head>
    <title>Authentication Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { color: #22c55e; margin-bottom: 10px; }
        p { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Authentication Successful</h1>
        <p>You can close this window and return to Langflow.</p>
    </div>
</body>
</html>"""
                self.wfile.write(html)

            def _send_error_response(self) -> None:
                """Send an error response to the browser."""
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                # Access outer handler's error info (intentional)
                error_msg = handler._error_description or handler._error or "Unknown error"  # noqa: SLF001
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Authentication Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{ color: #ef4444; margin-bottom: 10px; }}
        p {{ color: #666; }}
        .error {{ color: #dc2626; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Authentication Failed</h1>
        <p class="error">{error_msg}</p>
        <p>Please close this window and try again.</p>
    </div>
</body>
</html>""".encode()
                self.wfile.write(html)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                """Suppress default HTTP server logging."""

        # Create server on specified port
        # Bind to 127.0.0.1 for security (localhost only), but use self._host in the redirect_uri
        self._server = HTTPServer(("127.0.0.1", self._port), CallbackRequestHandler)
        actual_port = self._server.server_address[1]

        # Run server in background thread to handle one request
        thread = Thread(target=self._server.handle_request, daemon=True)
        thread.start()

        await logger.ainfo(f"OAuth callback server started on {self._host}:{actual_port}")
        return f"http://{self._host}:{actual_port}/callback"

    async def wait_for_callback(self, timeout: float = 300.0) -> tuple[str, str | None]:
        """Wait for the OAuth callback and return the authorization code.

        Args:
            timeout: Maximum time to wait for the callback in seconds.

        Returns:
            A tuple of (authorization_code, state).

        Raises:
            TimeoutError: If the callback is not received within the timeout.
            ValueError: If an OAuth error was received or no authorization code.
        """
        try:
            await asyncio.wait_for(self._received.wait(), timeout=timeout)
        except asyncio.TimeoutError as e:
            msg = f"OAuth callback timed out after {timeout} seconds"
            await logger.aerror(msg)
            raise TimeoutError(msg) from e

        if self._error:
            error_msg = self._error_description or self._error
            msg = f"OAuth error: {error_msg}"
            await logger.aerror(msg)
            raise ValueError(msg)

        if not self._auth_code:
            msg = "No authorization code received in OAuth callback"
            await logger.aerror(msg)
            raise ValueError(msg)

        await logger.ainfo("OAuth callback received successfully")
        return self._auth_code, self._state

    def shutdown(self) -> None:
        """Shutdown the callback server.

        Call this after receiving the callback or on cleanup.
        """
        if self._server:
            with contextlib.suppress(OSError):
                self._server.server_close()
            self._server = None


async def create_redirect_handler() -> Callable[[str], Coroutine[Any, Any, None]]:
    """Create a redirect handler that opens the authorization URL in a browser.

    Returns:
        An async function that takes an authorization URL and opens it in the browser.
    """

    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the user's default browser.

        Args:
            authorization_url: The OAuth authorization URL to open.
        """
        await logger.ainfo(f"Opening browser for OAuth authentication: {authorization_url[:50]}...")
        webbrowser.open(authorization_url)

    return redirect_handler


async def create_callback_handler(
    port: int = 18085,
    timeout: float = 300.0,
    host: str = "localhost",
) -> tuple[Callable[[], Coroutine[Any, Any, tuple[str, str | None]]], str, Callable[[], None]]:
    """Create a callback handler with a local HTTP server.

    This is a convenience function that sets up the callback infrastructure
    needed for the OAuth flow.

    Args:
        port: Port for the callback server. Default is 18085 (less common port).
        timeout: Maximum time to wait for callback in seconds.
        host: Host for redirect_uri. Default is "localhost" for OAuth compatibility.

    Returns:
        A tuple of (callback_handler_fn, redirect_uri, cleanup_fn):
        - callback_handler_fn: Async function that waits for and returns the callback
        - redirect_uri: The URI to use in the OAuth authorization request
        - cleanup_fn: Function to call to clean up the server
    """
    handler = OAuthCallbackHandler(port=port, host=host)
    redirect_uri = await handler.start()

    async def callback_handler() -> tuple[str, str | None]:
        """Wait for OAuth callback and return (auth_code, state)."""
        return await handler.wait_for_callback(timeout=timeout)

    def cleanup() -> None:
        """Clean up the callback server."""
        handler.shutdown()

    return callback_handler, redirect_uri, cleanup
