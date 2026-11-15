"""List the URLs of a website with Olostep."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.olostep.olostep_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    OlostepAPIError,
    olostep_request,
    require_http_url,
    split_list,
)

# Mapping a site reads its sitemaps and pages, which can take a minute or more.
MAP_TIMEOUT_SECONDS = 120.0
# Large sites come back in parts linked by a cursor; stop after this many parts.
MAX_CURSOR_PAGES = 10


class OlostepMapComponent(Component):
    """Return the URLs found on a website, one row per URL."""

    display_name = "Olostep Map"
    description = "List the URLs of a website with Olostep, optionally filtered by path or sorted by a search query."
    documentation = f"{DOCUMENTATION_URL}/features/maps"
    icon = "Olostep"
    name = "OlostepMap"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Olostep API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="Website URL",
            info="The http(s) URL of the website to map.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Optional. Sort the URLs by how relevant they are to this query.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="top_n",
            display_name="Top N",
            info="Optional. Return only this many URLs. 0 returns all of them.",
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="include_urls",
            display_name="Include Paths",
            info="Optional. Only return URLs matching these glob patterns, comma-separated, such as /blog/**.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_urls",
            display_name="Exclude Paths",
            info="Optional. Never return URLs matching these glob patterns, comma-separated, such as /careers/**.",
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for each Olostep request.",
            value=MAP_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="map_dataframe"),
    ]

    def map_site(self) -> list[Data]:
        """Return one ``Data`` per URL, with the URL as ``text``."""
        try:
            payload: dict[str, object] = {"url": require_http_url(self.url)}
            search_query = str(self.search_query or "").strip()
            if search_query:
                payload["search_query"] = search_query
            top_n = int(self.top_n or 0)
            if top_n > 0:
                payload["top_n"] = top_n
            for field in ("include_urls", "exclude_urls"):
                patterns = split_list(getattr(self, field, None))
                if patterns:
                    payload[field] = patterns

            urls: list[str] = []
            for _ in range(MAX_CURSOR_PAGES):
                body = olostep_request(
                    "POST",
                    "/v1/maps",
                    api_key=self.api_key,
                    timeout=float(self.timeout or MAP_TIMEOUT_SECONDS),
                    json=payload,
                )
                page = body.get("urls")
                if not isinstance(page, list):
                    msg = "Olostep API returned a map response without a urls list."
                    raise OlostepAPIError(msg)
                urls.extend(str(url) for url in page if url)
                cursor = body.get("cursor")
                if not cursor:
                    break
                payload["cursor"] = cursor
            else:
                msg = (
                    f"Olostep map results are incomplete after {MAX_CURSOR_PAGES} page requests. "
                    "Reduce Top N or narrow Include Paths."
                )
                raise OlostepAPIError(msg)
        except OlostepAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [Data(text=url, data={"url": url}) for url in urls]
        self.status = f"Found {len(data)} URLs."
        return data

    def map_dataframe(self) -> DataFrame:
        """Return the website's URLs as a table, one row per URL."""
        return DataFrame(self.map_site())
