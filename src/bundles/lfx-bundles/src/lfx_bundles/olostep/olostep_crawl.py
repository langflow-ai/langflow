"""Crawl a website with Olostep and return each page as markdown."""

from __future__ import annotations

import time

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.olostep.olostep_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    OlostepAPIError,
    olostep_request,
    require_http_url,
    split_list,
)

DEFAULT_WAIT_SECONDS = 180.0
POLL_INTERVAL_SECONDS = 3.0
# The crawl is told to stop this many seconds before the component stops waiting,
# because the API can take ~10 s past its own timeout to wrap up.
_API_STOP_MARGIN_SECONDS = 20.0
_MIN_API_TIMEOUT_SECONDS = 10
PAGES_PER_REQUEST = 100
_MAX_PAGE_REQUESTS = 100


class OlostepCrawlComponent(Component):
    """Crawl a website from a start URL and return one row per page."""

    display_name = "Olostep Crawl"
    description = "Crawl a website with Olostep and return each page's content as markdown."
    documentation = f"{DOCUMENTATION_URL}/features/crawls"
    icon = "Olostep"
    name = "OlostepCrawl"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Olostep API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="start_url",
            display_name="Start URL",
            info="The http(s) URL to start crawling from.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            info="The most pages to crawl.",
            value=10,
        ),
        MessageTextInput(
            name="include_urls",
            display_name="Include Paths",
            info="Optional. Only crawl URLs matching these glob patterns, comma-separated, such as /blog/**.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_urls",
            display_name="Exclude Paths",
            info="Optional. Never crawl URLs matching these glob patterns, comma-separated, such as /careers/**.",
            advanced=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            info="Optional. How many links deep to follow from the start URL. 0 means no limit.",
            value=0,
            advanced=True,
        ),
        FloatInput(
            name="wait_seconds",
            display_name="Max Wait (seconds)",
            info=(
                "How long to wait for the crawl to finish. The crawl stops in time and returns the pages done "
                "by then. Fetching the pages' content afterwards takes extra time."
            ),
            value=DEFAULT_WAIT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="crawl_dataframe"),
    ]

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Call the Olostep API with this component's key."""
        return olostep_request(method, path, api_key=self.api_key, timeout=DEFAULT_TIMEOUT_SECONDS, **kwargs)

    def crawl(self) -> list[Data]:
        """Start a crawl, wait for it, and return one ``Data`` per page with the markdown as ``text``."""
        wait_seconds = max(float(self.wait_seconds or DEFAULT_WAIT_SECONDS), _MIN_API_TIMEOUT_SECONDS)
        try:
            payload: dict[str, object] = {
                "start_url": require_http_url(self.start_url),
                "max_pages": max(int(self.max_pages or 1), 1),
                "timeout": max(int(wait_seconds - _API_STOP_MARGIN_SECONDS), _MIN_API_TIMEOUT_SECONDS),
            }
            for field in ("include_urls", "exclude_urls"):
                patterns = split_list(getattr(self, field, None))
                if patterns:
                    payload[field] = patterns
            max_depth = int(self.max_depth or 0)
            if max_depth > 0:
                payload["max_depth"] = max_depth

            crawl = self._request("POST", "/v1/crawls", json=payload)
            crawl_id = crawl.get("id")
            if not crawl_id:
                msg = "Olostep API returned a crawl response without an id."
                raise OlostepAPIError(msg)

            deadline = time.monotonic() + wait_seconds
            status = crawl.get("status")
            while status != "completed" and time.monotonic() < deadline:
                time.sleep(POLL_INTERVAL_SECONDS)
                status = self._request("GET", f"/v1/crawls/{crawl_id}").get("status")

            pages: list[dict] = []
            params: dict[str, object] = {"formats": "markdown", "limit": PAGES_PER_REQUEST}
            for _ in range(_MAX_PAGE_REQUESTS):
                body = self._request("GET", f"/v1/crawls/{crawl_id}/pages", params=params)
                batch = body.get("pages")
                if not isinstance(batch, list):
                    msg = "Olostep API returned a pages response without a pages list."
                    raise OlostepAPIError(msg)
                pages.extend(page for page in batch if isinstance(page, dict))
                cursor = body.get("cursor")
                if cursor is None or not batch:
                    break
                params["cursor"] = cursor
            else:
                msg = (
                    f"Olostep crawl results are incomplete after {_MAX_PAGE_REQUESTS} page requests. "
                    "Reduce Max Pages or narrow Include Paths."
                )
                raise OlostepAPIError(msg)
        except OlostepAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=str(page.get("markdown_content") or ""),
                data={
                    "url": page.get("url"),
                    "markdown_content": page.get("markdown_content") or "",
                    "crawl_id": crawl_id,
                },
            )
            for page in pages
        ]
        if status == "completed":
            self.status = f"Crawled {len(data)} pages."
        else:
            self.status = f"Crawl {crawl_id} was still running after {wait_seconds:g} s; returned {len(data)} pages."
        return data

    def crawl_dataframe(self) -> DataFrame:
        """Return the crawled pages as a table, one row per page."""
        return DataFrame(self.crawl())
