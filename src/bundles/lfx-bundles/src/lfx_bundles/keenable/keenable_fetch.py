"""Fetch a web page with Keenable and return its main content as markdown."""

from __future__ import annotations

from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.keenable.keenable_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    KeenableAPIError,
    keenable_request,
)


class KeenableFetchComponent(Component):
    """Fetch one page through Keenable.

    Keenable downloads the page on its own servers, so this component only sends
    the URL to ``api.keenable.ai`` and never opens a connection to the page itself.
    """

    display_name = "Keenable Fetch"
    description = "Fetch a web page with Keenable and return its main content as markdown. Works without an API key."
    documentation = DOCUMENTATION_URL
    icon = "Keenable"
    name = "KeenableFetch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Keenable API Key",
            info=API_KEY_INFO,
            required=False,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The http(s) URL of the page to fetch.",
            required=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Keenable to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Page", name="page", method="fetch_page"),
    ]

    def fetch_page(self) -> Data:
        """Return the page as one ``Data`` with the markdown content as ``text``."""
        url = str(self.url or "").strip()
        parsed = urlsplit(url)
        try:
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                msg = f"Enter an absolute http(s) URL, such as https://example.com; got {url!r}."
                raise KeenableAPIError(msg)
            body = keenable_request(
                "GET",
                "/v1/fetch/public",
                "/v1/fetch",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"url": url},
            )
        except KeenableAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        page = Data(text=str(body.get("content") or ""), data=body)
        self.status = page
        return page
