"""Tests for URLComponent input type configuration."""

import sys
import time
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


@pytest.fixture
def url_component_with_real_parser(monkeypatch):
    """Import URLComponent with only the non-parser dependencies stubbed.

    `_text_extractor` is what the parser does, so bs4 and lxml have to be real
    here; the other stubs keep the import cheap. Both live in lfx's `integration`
    extra rather than its base dependencies, which is why the fixture above stubs
    them and why these cases are skipped where they are not installed.
    """
    pytest.importorskip("bs4")
    pytest.importorskip("lxml")

    for mod in (
        "langchain_community",
        "langchain_community.document_loaders",
        "markitdown",
    ):
        monkeypatch.setitem(sys.modules, mod, MagicMock())
    # The other fixture may have imported this module with bs4 stubbed out.
    # `delitem` records nothing when the key is absent, so the module imported
    # below would outlive the test; `setitem` records the previous state.
    monkeypatch.setitem(sys.modules, "lfx.components.data_source.url", None)
    del sys.modules["lfx.components.data_source.url"]

    from lfx.components.data_source.url import URLComponent

    return URLComponent


class TestURLComponentTextExtraction:
    """Text pulled out of a page must keep the boundaries a reader sees."""

    def test_block_elements_do_not_run_together(self, url_component_with_real_parser):
        html = (
            "<html><body><h1>Quarterly Report</h1><p>Revenue rose.</p>"
            "<p>Costs fell.</p><ul><li>Item one</li><li>Item two</li></ul></body></html>"
        )

        text = url_component_with_real_parser._text_extractor(html)

        assert text == "Quarterly Report\nRevenue rose.\nCosts fell.\nItem one\nItem two"

    def test_inline_elements_keep_the_sentence_intact(self, url_component_with_real_parser):
        """A separator argument would fix the blocks and break this."""
        html = '<p>Hello <b>world</b>! See <a href="#">this</a>.</p>'

        assert url_component_with_real_parser._text_extractor(html) == "Hello world! See this."

    def test_the_title_reads_as_its_own_line(self, url_component_with_real_parser):
        """Not a block, but it is a line once the page is flattened."""
        html = "<html><head><title>Test Page</title></head><body><p>Body text</p></body></html>"

        assert url_component_with_real_parser._text_extractor(html) == "Test Page\nBody text"

    def test_a_line_break_element_becomes_a_line_break(self, url_component_with_real_parser):
        html = "<p>line one<br>line two</p>"

        assert url_component_with_real_parser._text_extractor(html) == "line one\nline two"

    def test_many_line_breaks_are_read_in_linear_time(self, url_component_with_real_parser):
        """Replacing each <br> in place scans its siblings every time, which is
        quadratic: 50,000 of them in one element took well over 10 s."""
        html = "<div>" + "x<br>" * 50_000 + "</div>"

        started = time.perf_counter()
        lines = url_component_with_real_parser._text_extractor(html).split("\n")
        elapsed = time.perf_counter() - started

        assert elapsed < 5
        assert len(lines) == 50_000
        assert set(lines) == {"x"}

    def test_script_and_style_contents_stay_out(self, url_component_with_real_parser):
        html = "<p>x</p><script>var a = 1;</script><style>.a{color:red}</style><p>y</p>"

        assert url_component_with_real_parser._text_extractor(html) == "x\ny"
