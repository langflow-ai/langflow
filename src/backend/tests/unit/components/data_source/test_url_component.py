"""Tests for the URL component.

The URL component fetches pages with ``httpx`` and enforces DNS-pinned SSRF
protection (see ``test_dns_rebinding.py`` for the rebinding-specific coverage).
These tests exercise content extraction, output formats, URL normalization, and
the SSRF guard without making real network requests by stubbing the per-URL
fetch (``_fetch_url_with_pinning``) and, for SSRF, validating direct IPs.
"""

import pytest
from lfx.components.data_source.url import URLComponent
from lfx.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


def _static_fetch(html: str, metadata: dict):
    """Build an async stand-in for ``URLComponent._fetch_url_with_pinning``.

    Returns the same ``(html, metadata)`` for every URL so tests can drive the
    extraction / formatting logic without any network access.
    """

    async def _fetch(_self, _url, _validated_ips, _headers):
        return html, metadata

    return _fetch


def _per_url_fetch(pages: dict):
    """Async stand-in returning ``(html, metadata)`` keyed by the requested URL.

    Unknown URLs yield empty content (treated as "nothing fetched").
    """

    async def _fetch(_self, url, _validated_ips, _headers):
        return pages.get(url, ("", {}))

    return _fetch


@pytest.fixture
def disable_ssrf(monkeypatch):
    """Disable SSRF protection so ``ensure_url`` skips DNS resolution."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")


class TestURLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return URLComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "urls": ["https://google.com"],
            "format": "Text",
            "max_depth": 1,
            "prevent_outside": True,
            "use_async": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return [
            {"version": "1.0.19", "module": "data", "file_name": "URL"},
            {"version": "1.1.0", "module": "data", "file_name": "url"},
            {"version": "1.1.1", "module": "data", "file_name": "url"},
            {"version": "1.2.0", "module": "data", "file_name": "url"},
        ]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_basic_functionality(self, monkeypatch):
        """Fetched content and metadata are surfaced on the output DataFrame."""
        metadata = {
            "source": "https://example.com",
            "title": "Test Page",
            "description": "Test Description",
            "content_type": "text/html",
            "language": "en",
        }
        monkeypatch.setattr(
            URLComponent,
            "_fetch_url_with_pinning",
            _static_fetch("<html><body>test content</body></html>", metadata),
        )
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "max_depth": 1, "format": "Text"})

        data_frame = await component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert len(data_frame) == 1

        row = data_frame.iloc[0]
        assert row["text"] == "test content"
        assert row["url"] == "https://example.com"
        assert row["title"] == "Test Page"
        assert row["description"] == "Test Description"
        assert row["content_type"] == "text/html"
        assert row["language"] == "en"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_multiple_urls(self, monkeypatch):
        """Each provided URL produces its own row."""
        pages = {
            "https://example.com": ("<html><body>first</body></html>", {"source": "https://example.com"}),
            "https://example.org": ("<html><body>second</body></html>", {"source": "https://example.org"}),
        }
        monkeypatch.setattr(URLComponent, "_fetch_url_with_pinning", _per_url_fetch(pages))
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com", "https://example.org"], "max_depth": 1})

        data_frame = await component.fetch_content()
        assert len(data_frame) == 2
        texts = set(data_frame["text"])
        assert texts == {"first", "second"}

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_text_format(self, monkeypatch):
        """Text format strips HTML tags to plain text."""
        html = "<html><body><h1>Heading</h1><p>Hello world</p></body></html>"
        monkeypatch.setattr(
            URLComponent, "_fetch_url_with_pinning", _static_fetch(html, {"source": "https://example.com"})
        )
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "format": "Text"})

        data_frame = await component.fetch_content()
        text = data_frame.iloc[0]["text"]
        assert "<h1>" not in text
        assert "Heading" in text
        assert "Hello world" in text

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_html_format(self, monkeypatch):
        """HTML format preserves the raw markup."""
        html = "<html><body><h1>Heading</h1><p>Hello world</p></body></html>"
        monkeypatch.setattr(
            URLComponent, "_fetch_url_with_pinning", _static_fetch(html, {"source": "https://example.com"})
        )
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "format": "HTML"})

        data_frame = await component.fetch_content()
        text = data_frame.iloc[0]["text"]
        assert "<h1>Heading</h1>" in text

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_markdown_format(self, monkeypatch):
        """Markdown format converts HTML headings/paragraphs to markdown."""
        html = "<html><body><h1>Heading</h1><p>Hello world</p></body></html>"
        monkeypatch.setattr(
            URLComponent, "_fetch_url_with_pinning", _static_fetch(html, {"source": "https://example.com"})
        )
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "format": "Markdown"})

        data_frame = await component.fetch_content()
        text = data_frame.iloc[0]["text"]
        assert "# Heading" in text
        assert "Hello world" in text

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_missing_metadata(self, monkeypatch):
        """Missing metadata fields default to empty strings."""
        monkeypatch.setattr(
            URLComponent,
            "_fetch_url_with_pinning",
            _static_fetch("<html><body>test content</body></html>", {"source": "https://example.com"}),
        )
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        data_frame = await component.fetch_content()
        row = data_frame.iloc[0]
        assert row["text"] == "test content"
        assert row["url"] == "https://example.com"
        assert row["title"] == ""
        assert row["description"] == ""
        assert row["content_type"] == ""
        assert row["language"] == ""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_error_handling_empty_urls(self):
        """An empty URL list raises a clear error."""
        component = URLComponent()
        component.set_attributes({"urls": []})
        with pytest.raises(ValueError, match="Error loading documents:"):
            await component.fetch_content()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("disable_ssrf")
    async def test_url_component_error_handling_no_documents(self, monkeypatch):
        """When no page yields content, a 'no documents' error is raised."""
        monkeypatch.setattr(URLComponent, "_fetch_url_with_pinning", _static_fetch("", {}))
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})
        with pytest.raises(ValueError, match="Error loading documents:"):
            await component.fetch_content()

    @pytest.mark.usefixtures("disable_ssrf")
    def test_url_component_ensure_url(self):
        """ensure_url normalizes the scheme and rejects malformed URLs."""
        component = URLComponent()

        # Missing scheme defaults to https; returns (url, pinned_ips).
        url, ips = component.ensure_url("example.com")
        assert url == "https://example.com"
        assert ips == []

        # Existing scheme is preserved.
        url, _ips = component.ensure_url("https://example.com")
        assert url == "https://example.com"

        # Malformed URL is rejected.
        with pytest.raises(ValueError, match="Invalid URL"):
            component.ensure_url("not a url")


class TestURLComponentSSRFProtection:
    """SSRF protection is enforced when ensuring and fetching URLs."""

    @pytest.fixture(autouse=True)
    def enable_ssrf(self, monkeypatch):
        """Enable SSRF protection with an empty allowlist for these tests."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    def test_ensure_url_blocks_localhost(self):
        """Loopback addresses are blocked."""
        component = URLComponent()
        with pytest.raises(ValueError, match="SSRF Protection"):
            component.ensure_url("http://127.0.0.1:8080")

    def test_ensure_url_blocks_private_ip(self):
        """RFC 1918 private addresses are blocked."""
        component = URLComponent()
        with pytest.raises(ValueError, match="SSRF Protection"):
            component.ensure_url("http://192.168.1.1/admin")

    def test_ensure_url_blocks_metadata_endpoint(self):
        """The cloud metadata endpoint is blocked."""
        component = URLComponent()
        with pytest.raises(ValueError, match="SSRF Protection"):
            component.ensure_url("http://169.254.169.254/latest/meta-data/")

    def test_ensure_url_allows_public_ip(self):
        """A public IP passes and is returned for DNS pinning."""
        component = URLComponent()
        url, ips = component.ensure_url("http://8.8.8.8/")
        assert url == "http://8.8.8.8/"
        assert ips == ["8.8.8.8"]

    @pytest.mark.asyncio
    async def test_ssrf_protection_in_fetch_content(self):
        """A blocked URL surfaces the SSRF error from fetch_content (not a generic message)."""
        component = URLComponent()
        component.set_attributes({"urls": ["http://127.0.0.1:9999"]})
        with pytest.raises(ValueError, match="SSRF Protection"):
            await component.fetch_url_contents()
