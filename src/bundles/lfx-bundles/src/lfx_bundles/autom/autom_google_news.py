"""Search Google News with Autom."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.autom.autom_common import (
    API_KEY_INFO,
    COUNTRY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    LANGUAGE_INFO,
    MAX_RESULTS_LIMIT,
    AutomAPIError,
    autom_get,
    clamp_max_results,
    organic_rows,
)


class AutomGoogleNewsComponent(Component):
    """Run a Google News search through Autom and return one row per article."""

    display_name = "Autom Google News"
    description = "Search Google News with Autom and get recent articles: title, link, source, date and snippet."
    documentation = DOCUMENTATION_URL
    icon = "Autom"
    name = "AutomGoogleNews"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Autom API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The news topic to search for.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"The number of articles to return, from 1 to {MAX_RESULTS_LIMIT}.",
            value=5,
            advanced=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info=COUNTRY_INFO,
            advanced=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info=LANGUAGE_INFO,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Autom to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="news_dataframe"),
    ]

    def news(self) -> list[Data]:
        """Return one ``Data`` per article, with the snippet as ``text``."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        params: dict[str, object] = {"query": query}
        country = str(self.country or "").strip().lower()
        if country:
            params["gl"] = country
        language = str(self.language or "").strip()
        if language:
            params["hl"] = language

        try:
            body = autom_get(
                "/v1/google/news",
                api_key=self.api_key,
                params=params,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            )
            rows = organic_rows(body)
        except AutomAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(text=str(row.get("snippet") or row.get("title") or ""), data=row)
            for row in rows[: clamp_max_results(self.max_results)]
        ]
        self.status = data
        return data

    def news_dataframe(self) -> DataFrame:
        return DataFrame(self.news())
