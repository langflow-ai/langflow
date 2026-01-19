"""MCP OAuth 2.1 support for Langflow.

This module provides OAuth 2.1 authentication support for MCP HTTP-based servers,
leveraging the MCP SDK's built-in OAuthClientProvider.

Only three components are implemented here:
1. TokenStorage implementations (in-memory and file-based)
2. redirect_handler (opens browser with auth URL)
3. callback_handler (local HTTP server to receive OAuth callback)
"""

from lfx.base.mcp.oauth.handlers import OAuthCallbackHandler
from lfx.base.mcp.oauth.provider import create_mcp_oauth_provider
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage

__all__ = [
    "FileTokenStorage",
    "InMemoryTokenStorage",
    "OAuthCallbackHandler",
    "create_mcp_oauth_provider",
]
