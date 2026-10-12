"""Tests for URLComponent input type configuration."""

import importlib.util
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def url_component(monkeypatch):
    """Import URLComponent with heavy third-party modules stubbed for this test."""
    for mod in (
        "langchain_community",
        "langchain_community.document_loaders",
        "markitdown",
        "bs4",
        "lxml",
    ):
        monkeypatch.setitem(sys.modules, mod, MagicMock())

    from lfx.components.data_source.url import URLComponent

    return URLComponent


@pytest.fixture
def url_module_without_markitdown(monkeypatch):
    """Load the URL component module as Python 3.15+ sees it: with markitdown not installed.

    The module is executed from source without registering it in ``sys.modules``, so the
    cached ``lfx.components.data_source.url`` other tests use is left untouched.
    """
    monkeypatch.setitem(sys.modules, "markitdown", None)  # makes `import markitdown` raise ImportError
    spec = importlib.util.find_spec("lfx.components.data_source.url")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestURLComponentWithoutMarkitdown:
    """markitdown is gated off Python 3.15+; only the Markdown output format may depend on it."""

    def test_module_imports_without_markitdown(self, url_module_without_markitdown):
        assert hasattr(url_module_without_markitdown, "URLComponent")

    def test_markdown_format_reports_missing_markitdown(self, url_module_without_markitdown):
        with pytest.raises(ImportError, match="Use the Text or HTML format instead"):
            url_module_without_markitdown.URLComponent._markdown_extractor("<h1>Heading</h1>")


class TestURLComponentInputTypes:
    """Verify the urls input accepts Message as an input type."""

    def test_urls_input_accepts_message_type(self, url_component):
        urls_input = next(inp for inp in url_component.inputs if inp.name == "urls")
        assert "Message" in urls_input.input_types

    def test_urls_input_is_list(self, url_component):
        urls_input = next(inp for inp in url_component.inputs if inp.name == "urls")
        assert urls_input.is_list is True

    def test_follow_redirects_input_defaults_to_true(self, url_component):
        """Redirects must be followed by default so canonical http->https / www hops resolve."""
        follow_redirects_input = next(inp for inp in url_component.inputs if inp.name == "follow_redirects")
        assert follow_redirects_input.value is True


class TestHeadersForRedirect:
    """Verify sensitive headers are only kept across same-origin (or https-upgrade) redirects."""

    HEADERS = {"Authorization": "Bearer token", "Cookie": "session=1", "User-Agent": "Test"}

    def test_same_origin_keeps_headers(self, url_component):
        result = url_component._headers_for_redirect(self.HEADERS, "https://a.test/x", "https://a.test/y")
        assert result == self.HEADERS

    def test_https_upgrade_keeps_headers(self, url_component):
        """Direct http->https upgrade on default ports keeps headers, matching httpx."""
        result = url_component._headers_for_redirect(self.HEADERS, "http://a.test/x", "https://a.test/x")
        assert result == self.HEADERS

    def test_https_downgrade_drops_sensitive_headers(self, url_component):
        """https->http is a different origin; credentials must not leak to plaintext."""
        result = url_component._headers_for_redirect(self.HEADERS, "https://a.test/x", "http://a.test/x")
        assert result == {"User-Agent": "Test"}

    def test_port_change_drops_sensitive_headers(self, url_component):
        """Same host on another port is a different origin (possibly a different service)."""
        result = url_component._headers_for_redirect(self.HEADERS, "https://a.test/x", "https://a.test:8443/x")
        assert result == {"User-Agent": "Test"}

    def test_cross_host_drops_sensitive_headers(self, url_component):
        result = url_component._headers_for_redirect(self.HEADERS, "https://a.test/x", "https://b.test/x")
        assert result == {"User-Agent": "Test"}

    def test_explicit_default_port_is_same_origin(self, url_component):
        result = url_component._headers_for_redirect(self.HEADERS, "https://a.test/x", "https://a.test:443/y")
        assert result == self.HEADERS
