"""MCP OAuth 2.1 support for Langflow.

This module provides OAuth 2.1 authentication support for MCP HTTP-based servers,
leveraging the MCP SDK's built-in OAuthClientProvider for all OAuth operations.

Components:
1. TokenStorage implementations (in-memory, file-based, and user-scoped)
2. OAuthStateManager for deployment-ready OAuth flows
3. SDK-based OAuth provider with automatic token refresh
4. OAuthFlowStarted exception for handling OAuth redirects
"""

from lfx.base.mcp.oauth.provider import (
    OAuthAuthWrapper,
    OAuthFlowStarted,
    OAuthFlowStartedError,
    OAuthRequiredError,
    create_deployed_oauth_provider,
    get_oauth_token_for_server,
    get_server_key,
)
from lfx.base.mcp.oauth.state_manager import OAuthStateManager, get_oauth_state_manager
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage, UserScopedTokenStorage

__all__ = [
    "FileTokenStorage",
    "InMemoryTokenStorage",
    "OAuthAuthWrapper",
    "OAuthFlowStarted",
    "OAuthFlowStartedError",
    "OAuthRequiredError",
    "OAuthStateManager",
    "UserScopedTokenStorage",
    "create_deployed_oauth_provider",
    "get_oauth_state_manager",
    "get_oauth_token_for_server",
    "get_server_key",
]
