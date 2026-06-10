"""SSRF protection tests for the legacy SearXNG Search tool component.

Both the config-autocomplete fetch (``update_build_config``) and the agent-invokable
search tool issue requests to a user-supplied base URL. With SSRF protection enabled
those URLs must be validated so they cannot reach internal services.
"""

import ipaddress
import os
import socket
from unittest.mock import Mock, patch

from lfx.components.tools.searxng import SearXNGToolComponent
from lfx.schema.dotdict import dotdict


def _resolve_public(host, *_args, **_kwargs):
    """socket.getaddrinfo stub: hostnames resolve to a public IP, literal IPs to themselves."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        ip = "93.184.216.34"
    else:
        ip = host
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


class TestSearXNGSSRFProtection:
    def test_update_build_config_blocks_internal_url(self):
        """Fetching the SearXNG /config from an internal URL is blocked; no request is made."""
        component = SearXNGToolComponent()
        build_config = dotdict(
            {
                "url": {"value": ""},
                "categories": {"options": [], "value": []},
                "language": {"options": []},
            }
        )

        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
        ):
            result = component.update_build_config(build_config, "http://169.254.169.254", "url")

        mock_get.assert_not_called()
        # The component records the failure rather than fetching internal data.
        assert result["categories"]["options"][0] == "Failed to parse"

    def test_search_tool_blocks_internal_url(self):
        """The agent-invokable search tool blocks an internal base URL; no request is made."""
        component = SearXNGToolComponent()
        component.url = "http://169.254.169.254"
        component.categories = ["general"]
        component.language = "en"
        component.max_results = 5

        tool = component.build_tool()

        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
        ):
            result = tool.func(query="secrets")

        mock_get.assert_not_called()
        assert isinstance(result, list)
        assert "Failed to search" in result[0]

    def test_search_tool_allows_public_url(self):
        """A public SearXNG instance still works with SSRF protection enabled."""
        component = SearXNGToolComponent()
        component.url = "http://searx.example.com"
        component.categories = ["general"]
        component.language = "en"
        component.max_results = 5

        tool = component.build_tool()

        search_response = Mock()
        search_response.status_code = 200
        search_response.headers = {}
        search_response.json = Mock(return_value={"results": [{"title": "a"}, {"title": "b"}]})

        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=search_response) as mock_get,
        ):
            result = tool.func(query="news")

        assert mock_get.call_count == 1
        assert len(result) == 2
