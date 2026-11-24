"""MCP HTTP client must not follow redirects after one-shot SSRF validation."""

from lfx.base.mcp.util import create_mcp_http_client_with_ssl_option


def test_mcp_http_client_does_not_follow_redirects():
    client = create_mcp_http_client_with_ssl_option(verify_ssl=True)
    assert client.follow_redirects is False


def test_mcp_http_client_no_redirects_when_ssl_disabled():
    client = create_mcp_http_client_with_ssl_option(verify_ssl=False)
    assert client.follow_redirects is False
