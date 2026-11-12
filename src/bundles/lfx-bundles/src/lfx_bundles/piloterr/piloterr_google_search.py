"""Search Google with Piloterr."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.piloterr.piloterr_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    PiloterrAPIError,
    json_object,
    piloterr_get,
)

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_RESULTS_LIMIT = 100


class PiloterrGoogleSearchComponent(Component):
    """Run a Google search through Piloterr and return one row per organic result."""

    display_name = "Piloterr Google Search"
    description = "Search Google with Piloterr and get the organic results: title, link, snippet and position."
    documentation = f"{DOCUMENTATION_URL}/v2/api-reference/google/search"
    icon = "Piloterr"
    name = "PiloterrGoogleSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Piloterr API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The query to search Google for. Google operators such as site: are supported.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"The number of results to request, from 1 to {MAX_RESULTS_LIMIT}.",
            value=10,
            advanced=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info="Two-letter country code to search from, such as us or fr.",
            advanced=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="Language code of the results, optionally with a region, such as en or en-gb.",
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            info="City or region to search from, such as Paris, France.",
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
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per organic result, with the snippet as ``text``."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        try:
            num = int(self.max_results)
        except (TypeError, ValueError):
            num = 10
        num = min(max(num, 1), MAX_RESULTS_LIMIT)
        params: dict[str, object] = {"query": query, "num": num}
        country = str(self.country or "").strip().lower()
        if country:
            params["gl"] = country
        language = str(self.language or "").strip()
        if language:
            params["hl"] = language
        location = str(self.location or "").strip()
        if location:
            params["location"] = location

        try:
            body = json_object(
                piloterr_get(
                    "/v2/google/search",
                    api_key=self.api_key,
                    params=params,
                    timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                )
            )
            rows = body.get("organic_results")
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                msg = "Piloterr API returned organic_results that is not a list."
                raise PiloterrAPIError(msg)
        except PiloterrAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(text=str(row.get("snippet") or row.get("title") or ""), data=row)
            for row in rows[:num]
            if isinstance(row, dict)
        ]
        self.status = data
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
