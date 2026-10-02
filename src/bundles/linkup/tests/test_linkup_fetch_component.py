"""Unit tests for the Linkup Fetch component (``lfx-linkup``).

``linkup-sdk`` is a hard runtime dep of the bundle, so the client class is
patched at the component module and returns real SDK response models.  No
network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from lfx_linkup import LinkupFetchComponent
from linkup import LinkupFetchResponse

CLIENT_PATCH_TARGET = "lfx_linkup.components.linkup.linkup_fetch.LinkupClient"

FETCH_RESPONSE = LinkupFetchResponse(
    markdown="# Example Domain\n\nThis domain is for use in examples.",
    favicon="https://example.com/favicon.ico",
)


def _mock_client(response: object) -> MagicMock:
    client = MagicMock()
    client.fetch.return_value = response
    return client


@pytest.fixture
def component() -> LinkupFetchComponent:
    """Build a LinkupFetchComponent with sensible defaults set."""
    c = LinkupFetchComponent()
    c.url = "https://example.com"
    c.linkup_api_key = "test-key"  # pragma: allowlist secret
    c.render_js = False
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert LinkupFetchComponent.__name__ == "LinkupFetchComponent"
    assert LinkupFetchComponent.icon == "Linkup"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.linkup_api_key = ""
    with patch(CLIENT_PATCH_TARGET) as mock_client_cls, pytest.raises(ValueError, match="Linkup API key is required"):
        component.linkup_fetch()
    mock_client_cls.assert_not_called()


def test_missing_url_raises(component):
    """An empty URL is rejected before calling the API."""
    component.url = ""
    with patch(CLIENT_PATCH_TARGET) as mock_client_cls, pytest.raises(ValueError, match="URL is required"):
        component.linkup_fetch()
    mock_client_cls.assert_not_called()


def test_fetch_returns_markdown(component):
    """The page markdown is returned as the message text."""
    client = _mock_client(FETCH_RESPONSE)
    with patch(CLIENT_PATCH_TARGET, return_value=client) as mock_client_cls:
        message = component.linkup_fetch()
    mock_client_cls.assert_called_once_with(api_key="test-key")  # pragma: allowlist secret
    client.fetch.assert_called_once_with("https://example.com", render_js=False, timeout=120.0)
    assert message.text == FETCH_RESPONSE.markdown


def test_fetch_passes_render_js(component):
    """Render JavaScript is forwarded to the SDK."""
    component.render_js = True
    client = _mock_client(FETCH_RESPONSE)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        component.linkup_fetch()
    assert client.fetch.call_args.kwargs["render_js"] is True


def test_api_errors_propagate(component):
    """SDK errors surface to the caller instead of being swallowed."""
    client = MagicMock()
    client.fetch.side_effect = RuntimeError("boom")
    with patch(CLIENT_PATCH_TARGET, return_value=client), pytest.raises(RuntimeError, match="boom"):
        component.linkup_fetch()


def test_tool_mode_exposes_a_linkup_specific_tool():
    """The agent-facing tool name must not collide with other fetch components."""
    component = LinkupFetchComponent(linkup_api_key="test-key", render_js=False)  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["linkup_fetch"]

    client = _mock_client(FETCH_RESPONSE)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        output = asyncio.run(tools[0].ainvoke({"url": "https://example.com"}))
    assert client.fetch.call_args.args == ("https://example.com",)
    assert "Example Domain" in str(output)
