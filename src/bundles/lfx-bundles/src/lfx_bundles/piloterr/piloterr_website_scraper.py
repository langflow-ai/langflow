"""Fetch a web page with Piloterr and return its readable text and HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.piloterr.piloterr_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    PiloterrAPIError,
    page_html,
    piloterr_get,
)

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_WAIT_SECONDS = 30
ENGINES = {
    "Crawler": "crawler",
    "Rendering": "rendering",
    "Web Unlocker": "webunlocker",
}
_SKIPPED_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
_BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "td", "th", "tr", "ul",
}  # fmt: skip


class _TextExtractor(HTMLParser):
    """Readable text of a page: drops scripts and styles, keeps one line per block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ARG002
        if tag == "title":
            self._in_title = True
        elif tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in "".join(self.parts).split("\n"))
        return "\n".join(line for line in lines if line)

    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def html_to_text(html: str) -> tuple[str, str]:
    """Return ``(title, text)`` for an HTML page."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.title(), parser.text()


class PiloterrWebsiteScraperComponent(Component):
    """Fetch one page through Piloterr.

    Piloterr downloads the page on its own infrastructure, so this component only
    sends the URL to ``api.piloterr.com`` and never opens a connection to the page itself.
    """

    display_name = "Piloterr Website Scraper"
    description = (
        "Fetch a web page with Piloterr, with a plain crawler, a headless browser for JavaScript pages, "
        "or a web unlocker for protected pages. Returns the readable text and the HTML."
    )
    documentation = DOCUMENTATION_URL
    icon = "Piloterr"
    name = "PiloterrWebsiteScraper"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Piloterr API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The http(s) URL of the page to fetch.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="engine",
            display_name="Engine",
            info=(
                "Crawler fetches the page over HTTP. Rendering loads it in a headless browser for JavaScript pages. "
                "Web Unlocker gets past anti-bot protection."
            ),
            options=list(ENGINES),
            value="Crawler",
        ),
        IntInput(
            name="wait_in_seconds",
            display_name="Wait (seconds)",
            info=f"Rendering only: extra seconds to wait after the page loads, from 0 to {MAX_WAIT_SECONDS}.",
            value=0,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Piloterr to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Page", name="page", method="fetch_page"),
    ]

    def fetch_page(self) -> Data:
        """Return the page as one ``Data`` with the readable text as ``text``."""
        url = str(self.url or "").strip()
        engine = ENGINES.get(str(self.engine or ""), "crawler")
        try:
            try:
                parsed = urlsplit(url)
                valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            except ValueError:  # e.g. an unmatched bracket in the host
                valid = False
            if not valid:
                msg = f"Enter an absolute http(s) URL, such as https://example.com; got {url!r}."
                raise PiloterrAPIError(msg)
            params: dict[str, object] = {"query": url}
            if engine == "rendering":
                try:
                    wait = int(self.wait_in_seconds or 0)
                except (TypeError, ValueError):
                    wait = 0
                if wait > 0:
                    params["wait_in_seconds"] = min(wait, MAX_WAIT_SECONDS)
            html = page_html(
                piloterr_get(
                    f"/v2/website/{engine}",
                    api_key=self.api_key,
                    params=params,
                    timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                )
            )
        except PiloterrAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        title, text = html_to_text(html)
        page = Data(text=text, data={"url": url, "engine": engine, "title": title, "text": text, "html": html})
        self.status = page
        return page
