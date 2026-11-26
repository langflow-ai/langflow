"""Read web pages through WebRouter and return their content as markdown."""

from __future__ import annotations

from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.webrouter.webrouter_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    PROVIDER_INFO,
    WebRouterComponentError,
    call_router,
    split_list,
)

MAX_URLS = 10


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:  # e.g. an unmatched bracket in the host
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


class WebRouterExtractComponent(Component):
    """Read one or more pages through WebRouter.

    The pages are fetched by the extraction provider WebRouter calls, on that
    provider's servers, so this component sends the URLs to the provider and never
    opens a connection to the pages itself.
    """

    display_name = "WebRouter Extract"
    description = (
        "Read web pages through WebRouter and return their main content as markdown. "
        "Routes each call to one of several extraction providers. Works without an API key."
    )
    documentation = DOCUMENTATION_URL
    icon = "WebRouter"
    name = "WebRouterExtract"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info=f"One to {MAX_URLS} http(s) URLs to read, separated by commas or new lines.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="provider",
            display_name="Provider",
            info=PROVIDER_INFO,
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Provider API Key",
            info=API_KEY_INFO,
            required=False,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the pages, including fallbacks.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Pages", name="pages", method="extract_dataframe"),
    ]

    def extract(self) -> list[Data]:
        """Return one ``Data`` per URL: the page as ``text``, or an ``error`` for a URL that could not be read."""
        urls = split_list(self.urls)
        timeout = float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
        try:
            if not urls:
                msg = "Enter at least one URL."
                raise WebRouterComponentError(msg)
            if len(urls) > MAX_URLS:
                msg = f"Enter at most {MAX_URLS} URLs; got {len(urls)}."
                raise WebRouterComponentError(msg)
            invalid = [url for url in urls if not _is_http_url(url)]
            if invalid:
                msg = f"Enter absolute http(s) URLs, such as https://example.com; got {invalid[0]!r}."
                raise WebRouterComponentError(msg)
            response = call_router(
                self.provider,
                self.api_key,
                lambda router, provider: router.extract(urls, provider=provider, format="markdown", timeout=timeout),
            )
        except WebRouterComponentError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=document.content,
                data={
                    "url": document.url,
                    "title": document.title,
                    "content": document.content,
                    "provider": response.provider,
                },
            )
            for document in response.documents
        ]
        data.extend(
            Data(text=failure.error, data={"url": failure.url, "error": failure.error}) for failure in response.failures
        )
        self.status = data
        return data

    def extract_dataframe(self) -> DataFrame:
        return DataFrame(self.extract())
