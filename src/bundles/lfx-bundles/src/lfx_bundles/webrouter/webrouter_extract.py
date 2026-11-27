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
    redact_error,
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
            info=f"One to {MAX_URLS} http(s) URLs to read, separated by whitespace or new lines. Commas stay in URLs.",
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
        urls = str(self.urls or "").split()
        timeout = float(DEFAULT_TIMEOUT_SECONDS if self.timeout is None else self.timeout)
        error_urls = []
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
            error_urls = urls
            provider = str(self.provider or "").strip().lower().removeprefix("extract:").split(":", 1)[0]
            if provider == "obscura":
                msg = (
                    "The local obscura backend is not supported. "
                    "Choose a remote extraction provider or leave Provider empty."
                )
                raise WebRouterComponentError(msg)
            response = call_router(
                self.provider,
                self.api_key,
                lambda router, provider: router.extract(urls, provider=provider, format="markdown", timeout=timeout),
            )
        except WebRouterComponentError as exc:
            detail = redact_error(str(exc), self.api_key)
            logger.error(detail)
            data = [Data(text=detail, data={"url": url, "error": detail}) for url in error_urls]
            if not data:
                data = [Data(text=detail, data={"error": detail})]
            self.status = data
            return data

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
        for failure in response.failures:
            detail = redact_error(failure.error, self.api_key)
            data.append(Data(text=detail, data={"url": failure.url, "error": detail}))
        self.status = data
        return data

    def extract_dataframe(self) -> DataFrame:
        return DataFrame(self.extract())
