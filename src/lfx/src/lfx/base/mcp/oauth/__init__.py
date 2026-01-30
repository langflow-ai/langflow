"""MCP OAuth 2.1 support for Langflow.

This module provides OAuth 2.1 authentication support for MCP HTTP-based servers,
leveraging the MCP SDK's built-in OAuthClientProvider.

Components:
1. TokenStorage implementations (in-memory and file-based)
2. redirect_handler (opens browser with auth URL)
3. callback_handler (local HTTP server to receive OAuth callback)
4. OAuthStateManager for deployment-ready OAuth flows
5. Deployment mode detection and token-based auth
"""

from lfx.base.mcp.oauth.handlers import OAuthCallbackHandler
from lfx.base.mcp.oauth.provider import (
    OAuthAuthWrapper,
    OAuthRequiredError,
    TokenAuth,
    create_mcp_oauth_provider,
    create_token_auth,
    get_server_key,
    is_deployed_mode,
)
from lfx.base.mcp.oauth.state_manager import OAuthStateManager, get_oauth_state_manager
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage

__all__ = [
    # Storage
    "FileTokenStorage",
    "InMemoryTokenStorage",
    # Provider and auth
    "OAuthAuthWrapper",
    "OAuthCallbackHandler",
    "OAuthRequiredError",
    "TokenAuth",
    "create_mcp_oauth_provider",
    "create_token_auth",
    # Deployment mode
    "get_server_key",
    "is_deployed_mode",
    # State management
    "OAuthStateManager",
    "get_oauth_state_manager",
]
