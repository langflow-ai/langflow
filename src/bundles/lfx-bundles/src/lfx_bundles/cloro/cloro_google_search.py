"""Search Google with cloro and return the organic results and the AI Overview."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.cloro.cloro_common import (
    API_KEY_INFO,
    COUNTRY_INFO,
    DEFAULT_COUNTRY,
    DOCUMENTATION_URL,
    CloroAPIError,
    cloro_request,
    sources_list,
    usable_url,
)


class CloroGoogleSearchComponent(Component):
    """Run a Google search through cloro and return one row per result."""

    display_name = "cloro Google Search"
    description = "Search Google with cloro. Returns the organic results and, optionally, the AI Overview."
    documentation = DOCUMENTATION_URL
    icon = "Cloro"
    name = "CloroGoogleSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="cloro API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The query to search Google for.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info=COUNTRY_INFO,
            value=DEFAULT_COUNTRY,
            advanced=True,
        ),
        BoolInput(
            name="include_ai_overview",
            display_name="Include AI Overview",
            info="Add the Google AI Overview, with its sources, as the first row. Costs 7 credits instead of 5.",
            value=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for cloro to answer.",
            value=60.0,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return the AI Overview (when present) and one ``Data`` per organic result."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        payload: dict[str, object] = {
            "query": query,
            "country": str(self.country or DEFAULT_COUNTRY).strip().upper(),
        }
        if self.include_ai_overview:
            payload["include"] = {"aioverview": True}

        try:
            result = cloro_request(
                "/v1/monitor/google", payload, api_key=self.api_key, timeout=float(self.timeout or 60.0)
            )
        except CloroAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        rows: list[Data] = []
        overview = result.get("aioverview")
        if isinstance(overview, dict) and overview.get("text"):
            text = str(overview["text"])
            rows.append(
                Data(
                    text=text,
                    data={
                        "type": "ai_overview",
                        "position": 0,
                        "title": "AI Overview",
                        "link": "",
                        "snippet": text,
                        "sources": sources_list(overview.get("sources")),
                    },
                )
            )

        # A result whose link is empty or a Google redirect has no usable destination, so it is skipped.
        for item in result.get("organicResults") or []:
            link = usable_url(item.get("link")) if isinstance(item, dict) else ""
            if not link:
                continue
            title = str(item.get("title") or "")
            snippet = str(item.get("snippet") or "")
            rows.append(
                Data(
                    text=snippet or title,
                    data={
                        "type": "organic",
                        "position": item.get("position"),
                        "title": title,
                        "link": link,
                        "snippet": snippet,
                        "sources": [],
                    },
                )
            )

        self.status = rows
        return rows

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
