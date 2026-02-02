"""MCP OAuth 2.1 support for Langflow.

This module provides OAuth 2.1 authentication support for MCP HTTP-based servers,
leveraging the MCP SDK's built-in OAuthClientProvider for all OAuth operations.
"""

from lfx.base.mcp.oauth.provider import (
    OAuthAuthWrapper,
    OAuthRequiredError,
    create_deployed_oauth_provider,
    get_server_key,
)
from lfx.base.mcp.oauth.state_manager import get_oauth_state_manager
from lfx.base.mcp.oauth.storage import UserScopedTokenStorage

__all__ = [
    "OAuthAuthWrapper",
    "OAuthRequiredError",
    "UserScopedTokenStorage",
    "create_deployed_oauth_provider",
    "get_oauth_state_manager",
    "get_server_key",
]
