"""Tests for the URL component.

The URL component fetches pages with ``httpx`` and enforces DNS-pinned SSRF
protection (see ``test_dns_rebinding.py`` for the rebinding-specific coverage).
These tests exercise content extraction, output formats, URL normalization, and
the SSRF guard without making real network requests by stubbing the per-URL
fetch (``_fetch_url_with_pinning``) and, for SSRF, validating direct IPs. The
response-size limits are exercised at the connection level with httpcore mock
streams, so the real httpx streaming and decoding code runs.
"""

import gzip
import socket
import zlib
from types import SimpleNamespace

import httpcore
import pytest
from lfx.components.data_source import url as url_module
from lfx.components.data_source.url import URLComponent
from lfx.schema import DataFrame
from lfx.services.settings.base import Settings

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

    @pytest.fixture
    def skipped_outputs(self):
        return dict.fromkeys(["page_results", "raw_results"], "crawls the live URLs in default_kwargs")

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


def _http(status: str, headers: dict[str, str], *chunks: bytes) -> list[bytes]:
    """Raw HTTP/1.1 response: the head, then each body chunk as a separate network read."""
    head = f"HTTP/1.1 {status}\r\nConnection: close\r\n"
    head += "".join(f"{name}: {value}\r\n" for name, value in headers.items())
    return [f"{head}\r\n".encode(), *chunks]


class _RecordingStream(httpcore.AsyncMockStream):
    """Mock connection that records the request bytes; unread response chunks stay in ``_buffer``."""

    def __init__(self, buffer: list[bytes]):
        """Initialize the response chunks and captured request bytes."""
        super().__init__(buffer)
        self.sent = b""

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:  # noqa: ARG002
        """Capture outgoing request bytes for header assertions."""
        self.sent += buffer


class TestURLComponentResponseLimits:
    """Untrusted response bodies are read bounded, so a hostile server cannot exhaust memory."""

    LIMIT = 1024

    @pytest.fixture(autouse=True)
    def small_limits(self, monkeypatch):
        """Use small response limits and deterministic public DNS without network access."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", str(self.LIMIT))
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", str(url_module.FALLBACK_MAX_TOTAL_BYTES))
        monkeypatch.setattr(
            url_module, "get_settings_service", lambda: SimpleNamespace(settings=Settings(_env_file=None))
        )
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))],
        )

    @pytest.fixture(params=["true", "false"], ids=["ssrf-pinned", "ssrf-disabled"])
    def ssrf_mode(self, request, monkeypatch):
        """Run against both fetch paths: pinned per-hop redirects and httpx-built redirects."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", request.param)

    @pytest.fixture
    def serve(self, monkeypatch):
        """Answer each new connection with the next raw response; return the opened connections."""

        def _serve(*responses: list[bytes]) -> list[_RecordingStream]:
            """Queue response chunks and expose each connection for read assertions."""
            queue = list(responses)
            streams: list[_RecordingStream] = []

            async def connect_tcp(*_args, **_kwargs):
                """Replace a TCP connection with the next queued response."""
                streams.append(_RecordingStream(queue.pop(0)))
                return streams[-1]

            monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect_tcp)
            return streams

        return _serve

    @staticmethod
    def _component(**overrides) -> URLComponent:
        """Build a single-page HTML fetcher with explicit failure handling."""
        component = URLComponent()
        component.set_attributes(
            {"urls": ["http://site.test/"], "max_depth": 1, "format": "HTML", "continue_on_failure": False, **overrides}
        )
        return component

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("ssrf_mode")
    async def test_declared_oversized_body_is_rejected_unread(self, serve):
        """Reject an excessive Content-Length before consuming response body chunks."""
        body = b"x" * self.LIMIT
        streams = serve(_http("200 OK", {"Content-Length": str(2 * self.LIMIT)}, body, body))

        with pytest.raises(ValueError, match=f"exceeds the {self.LIMIT} byte limit"):
            await self._component().fetch_url_contents()

        assert len(streams[0]._buffer) == 2, "no body chunk should be read"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("ssrf_mode")
    async def test_undeclared_body_stops_streaming_at_limit(self, serve):
        """Stop an unknown-length response as soon as its body exceeds the cap."""
        streams = serve(_http("200 OK", {}, *[b"x" * 512] * 100))

        with pytest.raises(ValueError, match=f"exceeds the {self.LIMIT} byte limit"):
            await self._component().fetch_url_contents()

        assert len(streams[0]._buffer) > 90, "the transfer must be abandoned right after the limit"

    @pytest.mark.asyncio
    async def test_limit_applies_to_decoded_size(self, serve):
        """Reject compressed content whose expanded body exceeds the response cap."""
        bomb = gzip.compress(b"\0" * (100 * self.LIMIT))
        assert len(bomb) < self.LIMIT
        serve(_http("200 OK", {"Content-Encoding": "gzip", "Content-Length": str(len(bomb))}, bomb))

        with pytest.raises(ValueError, match=f"exceeds the {self.LIMIT} byte limit"):
            await self._component().fetch_url_contents()

    @pytest.mark.asyncio
    async def test_gzip_body_is_decoded_and_only_bounded_codings_are_advertised(self, serve):
        """Decode supported gzip responses and advertise only supported compression."""
        body = gzip.compress(b"<html><body>compressed page</body></html>")
        streams = serve(_http("200 OK", {"Content-Encoding": "gzip", "Content-Length": str(len(body))}, body))

        result = await self._component().fetch_url_contents()

        assert "compressed page" in result[0]["text"]
        assert b"accept-encoding: gzip, deflate\r\n" in streams[0].sent.lower()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("ssrf_mode")
    @pytest.mark.parametrize("coding", ["gzip", "deflate"])
    @pytest.mark.parametrize("separate_tail", [False, True], ids=["same-chunk", "later-chunk"])
    async def test_compressed_trailing_data_is_rejected(self, serve, coding, separate_tail):
        """Reject bytes following compressed EOF in the same or a later network chunk."""
        compress = gzip.compress if coding == "gzip" else zlib.compress
        encoded = compress(b"<html><body>small page</body></html>")
        tail = b"x" * 128
        chunks = [encoded, tail] if separate_tail else [encoded + tail]
        assert sum(map(len, chunks)) < self.LIMIT
        serve(_http("200 OK", {"Content-Encoding": coding}, *chunks))

        with pytest.raises(ValueError, match="Trailing data after compressed response"):
            await self._component().fetch_url_contents()

    @pytest.mark.asyncio
    async def test_encoded_bytes_are_bounded_even_without_decoded_output(self, serve):
        """Apply the byte cap to gzip metadata that emits no decoded content."""
        encoded = gzip.compress(b"<html>small page</html>")
        # Gzip's optional filename is consumed without producing decoded body bytes.
        header = encoded[:3] + b"\x08" + encoded[4:10]
        streams = serve(
            _http("200 OK", {"Content-Encoding": "gzip"}, header, b"x" * 512, b"x" * 512, b"\0" + encoded[10:])
        )

        with pytest.raises(ValueError, match="exceeds"):
            await self._component().fetch_url_contents()

        assert len(streams[0]._buffer) == 1, "stop reading the oversized encoded header before the body"

    @pytest.mark.asyncio
    async def test_rejected_encoded_bytes_exhaust_the_shared_budget(self, serve, monkeypatch):
        """Charge rejected encoded input so failure continuation cannot bypass the fetch cap."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", str(self.LIMIT))
        encoded = gzip.compress(b"<html>small page</html>")
        header = encoded[:3] + b"\x08" + encoded[4:10]
        streams = serve(
            _http("200 OK", {"Content-Encoding": "gzip"}, header, b"x" * 512, b"x" * 512, b"\0" + encoded[10:]),
            _http("200 OK", {}, b"<html>must not be fetched</html>"),
        )
        component = self._component(urls=["http://site.test/", "http://site.test/next"], continue_on_failure=True)

        with pytest.raises(ValueError, match="No documents were successfully loaded"):
            await component.fetch_url_contents()

        assert component._bytes_remaining <= 0
        assert len(streams) == 1, "rejected compressed bytes must still stop later URL fetches"

    @pytest.mark.asyncio
    async def test_corrupt_compressed_output_exhausts_the_shared_budget(self, serve, monkeypatch):
        """Charge reserved decoder output when a checksum error discards the decoded bytes."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", str(self.LIMIT))
        encoded = gzip.compress(b"x" * self.LIMIT)
        # Corrupt the CRC after zlib has expanded the full page within the same call.
        encoded = encoded[:-8] + bytes([encoded[-8] ^ 1]) + encoded[-7:]
        streams = serve(
            _http("200 OK", {"Content-Encoding": "gzip"}, encoded),
            _http("200 OK", {}, b"<html>must not be fetched</html>"),
        )
        component = self._component(urls=["http://site.test/", "http://site.test/next"], continue_on_failure=True)

        with pytest.raises(ValueError, match="No documents were successfully loaded"):
            await component.fetch_url_contents()

        assert component._bytes_remaining <= 0
        assert len(streams) == 1, "a checksum failure must not refund the decoder's output budget"

    @pytest.mark.asyncio
    async def test_decompression_is_bounded_before_output_is_allocated(self, serve, monkeypatch):
        """Require bounded zlib output on every call before accumulating decoded bytes."""
        original_decompressobj = zlib.decompressobj
        calls = []

        class RecordingDecompressor:
            """Record allocation limits while delegating to the real zlib decoder."""

            def __init__(self, *args, **kwargs):
                """Create the wrapped decoder and initialize its decoded byte counter."""
                self.decoder = original_decompressobj(*args, **kwargs)
                self.decoded_bytes = 0

            def __getattr__(self, name):
                """Expose zlib stream state through the recording wrapper."""
                return getattr(self.decoder, name)

            def decompress(self, data, max_length=0):
                """Record the requested output cap and return actual decompressed bytes."""
                calls.append((max_length, TestURLComponentResponseLimits.LIMIT - self.decoded_bytes + 1))
                decoded = self.decoder.decompress(data, max_length)
                self.decoded_bytes += len(decoded)
                return decoded

        monkeypatch.setattr(zlib, "decompressobj", RecordingDecompressor)
        encoded = gzip.compress(b"x" * (4 * self.LIMIT))
        serve(_http("200 OK", {"Content-Encoding": "gzip"}, encoded[:10], encoded[10:]))

        with pytest.raises(ValueError, match="exceeds"):
            await self._component().fetch_url_contents()

        assert calls
        assert all(0 < max_length <= remaining for max_length, remaining in calls), (
            "every decoder call must cap output at the remaining byte budget plus one overflow byte"
        )

    @staticmethod
    def _compress_body(body: bytes, coding: str) -> bytes:
        """Encode a response using gzip, zlib-wrapped deflate, or raw deflate."""
        if coding == "gzip":
            return gzip.compress(body)
        encoder = zlib.compressobj(wbits=-zlib.MAX_WBITS if coding == "raw-deflate" else zlib.MAX_WBITS)
        return encoder.compress(body) + encoder.flush()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("ssrf_mode")
    @pytest.mark.parametrize("coding", ["gzip", "deflate", "raw-deflate"])
    async def test_compressed_response_with_fragmented_headers_and_body(self, serve, coding):
        """Preserve supported decoding when every encoded byte arrives separately."""
        body = b"<html><body>fragmented compressed page</body></html>"
        encoded = self._compress_body(body, coding)
        content_encoding = "deflate" if coding == "raw-deflate" else coding
        chunks = [encoded[i : i + 1] for i in range(len(encoded))]
        serve(_http("200 OK", {"Content-Encoding": content_encoding}, *chunks))

        result = await self._component().fetch_url_contents()

        assert result[0]["text"] == body.decode()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("coding", ["gzip", "deflate", "raw-deflate"])
    async def test_compressed_response_exactly_at_limit_succeeds(self, serve, monkeypatch, coding):
        """Accept decoded content that exactly consumes both configured byte limits."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", str(self.LIMIT))
        body = b"x" * self.LIMIT
        encoded = self._compress_body(body, coding)
        content_encoding = "deflate" if coding == "raw-deflate" else coding
        serve(_http("200 OK", {"Content-Encoding": content_encoding}, encoded))
        component = self._component()

        result = await component.fetch_url_contents()

        assert result[0]["text"] == body.decode()
        assert component._bytes_remaining == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("coding", ["gzip", "deflate", "raw-deflate"])
    @pytest.mark.parametrize("damage", ["truncated", "corrupt"])
    async def test_incomplete_or_corrupt_compressed_response_is_rejected(self, serve, coding, damage):
        """Reject incomplete streams and invalid compressed data instead of returning partial pages."""
        encoded = self._compress_body(b"<html><body>small page</body></html>", coding)
        if damage == "truncated":
            encoded = encoded[:-4] if coding == "gzip" else encoded[:-1]
        elif coding == "raw-deflate":
            encoded = b"\x06"  # Invalid reserved DEFLATE block type.
        else:
            encoded = encoded[:-1] + bytes([encoded[-1] ^ 1])
        content_encoding = "deflate" if coding == "raw-deflate" else coding
        serve(_http("200 OK", {"Content-Encoding": content_encoding}, encoded))

        with pytest.raises(ValueError, match=r"(Incomplete|Invalid) compressed response"):
            await self._component().fetch_url_contents()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("coding", ["br", "zstd", "gzip, gzip"])
    async def test_codings_with_unbounded_expansion_are_rejected(self, serve, coding):
        """Reject unsupported compression and stacked content encodings."""
        serve(_http("200 OK", {"Content-Encoding": coding, "Content-Length": "4"}, b"abcd"))

        with pytest.raises(ValueError, match="Unsupported content encoding"):
            await self._component().fetch_url_contents()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("ssrf_mode")
    async def test_redirect_body_is_never_read(self, serve):
        """Follow redirects without consuming their potentially oversized bodies."""
        final = b"<html><body>final page</body></html>"
        streams = serve(
            _http("302 Found", {"Location": "/final"}, *[b"x" * 512] * 100),
            _http("200 OK", {"Content-Length": str(len(final))}, final),
        )

        result = await self._component().fetch_url_contents()

        assert "final page" in result[0]["text"]
        assert len(streams[0]._buffer) == 100, "the redirect body must not be read"

    @pytest.mark.asyncio
    async def test_redirects_without_pinning_keep_httpx_cookie_and_cap_semantics(self, serve, monkeypatch):
        """Preserve redirect cookies and hop limits when SSRF protection is disabled."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        final = b"<html><body>final page</body></html>"
        streams = serve(
            _http("302 Found", {"Location": "/final", "Set-Cookie": "session=abc; Path=/", "Content-Length": "0"}),
            _http("200 OK", {"Content-Length": str(len(final))}, final),
        )
        assert "final page" in (await self._component().fetch_url_contents())[0]["text"]
        assert b"cookie: session=abc\r\n" in streams[1].sent.lower()

        redirect = _http("302 Found", {"Location": "/again", "Content-Length": "0"})
        streams = serve(*[list(redirect) for _ in range(url_module.MAX_REDIRECTS + 1)])
        with pytest.raises(ValueError, match="Exceeded maximum allowed redirects"):
            await self._component().fetch_url_contents()
        assert len(streams) == url_module.MAX_REDIRECTS + 1

    @pytest.mark.asyncio
    async def test_total_budget_stops_crawl_and_resets_per_fetch(self, serve, monkeypatch):
        """Stop linked-page fetches at the shared cap and restore the budget on the next run."""
        root = b"<html><body>" + b"".join(b'<a href="/p%d">p</a>' % i for i in range(5)) + b"</body></html>"
        page = b"<html><body>" + b"x" * 400 + b"</body></html>"
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", str(len(root) + 2 * len(page)))

        def pages() -> list[list[bytes]]:
            """Create fresh mock responses for a root page and its linked pages."""
            return [_http("200 OK", {"Content-Length": str(len(body))}, body) for body in [root, *[page] * 5]]

        component = self._component(max_depth=2)
        for _ in range(2):
            streams = serve(*pages())
            result = await component.fetch_url_contents()
            assert [doc["url"] for doc in result] == ["http://site.test/", "http://site.test/p0", "http://site.test/p1"]
            assert len(streams) == 3, "no page may be requested once the budget is spent"


class TestURLComponentByteLimitEnvVars:
    """Check the resolver's defaults and handling of invalid environment values."""

    def test_defaults_when_unset(self, monkeypatch):
        """Use fallback caps when neither settings nor environment values are available."""
        monkeypatch.delenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", raising=False)
        monkeypatch.delenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", raising=False)
        monkeypatch.setattr(url_module, "get_settings_service", lambda: None)
        response_limit, total_limit = URLComponent._resolve_byte_limits()
        assert response_limit == url_module.FALLBACK_MAX_RESPONSE_BYTES
        assert total_limit == url_module.FALLBACK_MAX_TOTAL_BYTES

    def test_env_vars_override_the_defaults(self, monkeypatch):
        """Resolve configured environment values through the settings service."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", "2048")
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", "4096")
        monkeypatch.setattr(
            url_module, "get_settings_service", lambda: SimpleNamespace(settings=Settings(_env_file=None))
        )
        response_limit, total_limit = URLComponent._resolve_byte_limits()
        assert response_limit == 2048
        assert total_limit == 4096

    def test_settings_service_precedence_over_process_environment(self, monkeypatch):
        """Honor settings-service overrides ahead of direct process environment values."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", "2048")
        settings = Settings(_env_file=None)
        settings.url_component_max_response_bytes = 4096
        monkeypatch.setattr(
            url_module,
            "get_settings_service",
            lambda: SimpleNamespace(settings=settings),
        )
        response_limit, _ = URLComponent._resolve_byte_limits()
        assert response_limit == 4096

    def test_non_integer_env_var_falls_back_to_default(self, monkeypatch):
        """Keep a safe standalone default when an environment value is not an integer."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", "not-a-number")
        monkeypatch.setattr(url_module, "get_settings_service", lambda: None)
        response_limit, _ = URLComponent._resolve_byte_limits()
        assert response_limit == url_module.FALLBACK_MAX_RESPONSE_BYTES

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_non_positive_env_vars_fall_back_to_defaults(self, monkeypatch, value):
        """Replace non-positive standalone caps with their safe fallback values."""
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", value)
        monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", value)
        monkeypatch.setattr(url_module, "get_settings_service", lambda: None)
        assert URLComponent._resolve_byte_limits() == (
            url_module.FALLBACK_MAX_RESPONSE_BYTES,
            url_module.FALLBACK_MAX_TOTAL_BYTES,
        )
