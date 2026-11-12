"""Search Google with Autom."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
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

# Display label -> Google ``tbs`` value.
TIME_RANGES = {
    "Any time": "",
    "Past day": "qdr:d",
    "Past week": "qdr:w",
    "Past month": "qdr:m",
    "Past year": "qdr:y",
}


class AutomGoogleSearchComponent(Component):
    """Run a Google search through Autom and return one row per organic result."""

    display_name = "Autom Google Search"
    description = "Search Google with Autom and get the organic results: title, link, snippet and position."
    documentation = DOCUMENTATION_URL
    icon = "Autom"
    name = "AutomGoogleSearch"

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
            info="The query to search Google for. Google operators such as site: are supported.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"The number of results to return, from 1 to {MAX_RESULTS_LIMIT}.",
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
        MessageTextInput(
            name="location",
            display_name="Location",
            info="City or region to search from, such as Paris, France.",
            advanced=True,
        ),
        DropdownInput(
            name="time_range",
            display_name="Time Range",
            info="Only return pages published in this period.",
            options=list(TIME_RANGES),
            value="Any time",
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
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per organic result, with the snippet as ``text``."""
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
        location = str(self.location or "").strip()
        if location:
            params["location"] = location
        tbs = TIME_RANGES.get(str(self.time_range or ""), "")
        if tbs:
            params["tbs"] = tbs

        try:
            body = autom_get(
                "/v1/google/search",
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

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
