"""Scrape a web page with Olostep and return its content as markdown."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.olostep.olostep_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    OlostepAPIError,
    olostep_request,
    require_http_url,
)


class OlostepScrapeComponent(Component):
    """Scrape one page through Olostep.

    Olostep loads the page on its own servers, including JavaScript-rendered pages,
    so this component only sends the URL to ``api.olostep.com``.
    """

    display_name = "Olostep Scrape"
    description = "Scrape a web page with Olostep and return its content as clean markdown."
    documentation = f"{DOCUMENTATION_URL}/features/scrapes"
    icon = "Olostep"
    name = "OlostepScrape"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Olostep API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The http(s) URL of the page to scrape.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info="Load the page from this country, such as US, GB or IN. Leave empty for the default.",
            advanced=True,
        ),
        IntInput(
            name="wait_before_scraping",
            display_name="Wait Before Scraping (ms)",
            info="Milliseconds to wait for the page to load before reading it. Useful for pages that render late.",
            value=0,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Olostep to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Page", name="page", method="scrape_page"),
    ]

    def scrape_page(self) -> Data:
        """Return the page as one ``Data`` with the markdown content as ``text``."""
        try:
            url = require_http_url(self.url)
            payload: dict[str, object] = {"url_to_scrape": url, "formats": ["markdown"]}
            country = str(self.country or "").strip()
            if country:
                payload["country"] = country.upper()
            wait = int(self.wait_before_scraping or 0)
            if wait > 0:
                payload["wait_before_scraping"] = wait
            body = olostep_request(
                "POST",
                "/v1/scrapes",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                json=payload,
            )
        except OlostepAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        result = body.get("result") or {}
        markdown = str(result.get("markdown_content") or "")
        page = Data(
            text=markdown,
            data={
                "id": body.get("id"),
                "url": body.get("url") or body.get("url_to_scrape") or url,
                "markdown_content": markdown,
                "page_metadata": result.get("page_metadata"),
            },
        )
        self.status = page
        return page
