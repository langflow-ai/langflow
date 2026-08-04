from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import DOCUMENTATION, Endpoint, ScavioAPIMixin, api_key_input

ENDPOINTS = {
    "Google Search": Endpoint(
        path="/api/v2/google",
        credits=1,
        fields=(
            "query",
            "device",
            "start",
            "hl",
            "gl",
            "google_domain",
            "location",
            "uule",
            "lr",
            "cr",
            "safe",
            "nfpr",
            "filter",
            "time_period",
            "include_html",
            "resolve_ai_overview",
        ),
        required=("query",),
        result_keys=("organic_results",),
        send_false=("resolve_ai_overview",),
    ),
}


class ScavioSearchComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Search API"
    description = (
        "**Scavio** is a real-time search API for AI agents - a unified API over Google, "
        "YouTube, Amazon, Walmart, Reddit, TikTok, TikTok Shop, Instagram, X and LinkedIn. "
        "A cost-effective Tavily and SerpAPI alternative that returns clean JSON. "
        "This component runs a Google web search (`POST /api/v2/google`, 1 credit)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioSearch"

    ENDPOINTS = ENDPOINTS
    DEFAULT_ENDPOINT = "Google Search"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with Scavio.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country (gl)",
            info="Two-letter geo country code, e.g. us. Replaces v1's country_code.",
            advanced=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language (hl)",
            info="Two-letter interface language code, e.g. en. Replaces v1's language.",
            advanced=True,
        ),
        MessageTextInput(
            name="google_domain",
            display_name="Google Domain",
            info="Google domain to search, e.g. google.co.uk.",
            advanced=True,
        ),
        DropdownInput(
            name="device",
            display_name="Device",
            info="Device profile to emulate.",
            options=["", "desktop", "mobile"],
            value="",
            advanced=True,
        ),
        IntInput(
            name="start",
            display_name="Start Offset",
            info="Result offset, not a page number: 0 is page 1, 10 is page 2, and so on. Max 990.",
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            info="Canonical location name, e.g. Austin, Texas, United States.",
            advanced=True,
        ),
        MessageTextInput(
            name="uule",
            display_name="UULE",
            info="Pre-encoded UULE location string. Takes priority over Location.",
            advanced=True,
        ),
        MessageTextInput(
            name="lr",
            display_name="Language Restrict (lr)",
            info="Restrict results to a language, e.g. lang_en.",
            advanced=True,
        ),
        MessageTextInput(
            name="cr",
            display_name="Country Restrict (cr)",
            info="Restrict results to a country, e.g. countryUS.",
            advanced=True,
        ),
        DropdownInput(
            name="safe",
            display_name="Safe Search",
            info="Set to active to turn SafeSearch on. Leave empty to turn it off.",
            options=["", "active"],
            value="",
            advanced=True,
        ),
        DropdownInput(
            name="filter",
            display_name="Similar Results Filter",
            info="0 disables Google's similar and omitted result filtering. 1 keeps it on.",
            options=["", "0", "1"],
            value="",
            advanced=True,
        ),
        DropdownInput(
            name="time_period",
            display_name="Time Period",
            info="Restrict results to a recent time window.",
            options=["", "last_hour", "last_day", "last_week", "last_month", "last_year"],
            value="",
            advanced=True,
        ),
        BoolInput(
            name="nfpr",
            display_name="No Autocorrect",
            info="Disable Google's spelling autocorrection.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="include_html",
            display_name="Include Raw HTML",
            info="Add Google's raw HTML to the response under the html key.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="resolve_ai_overview",
            display_name="Resolve AI Overview",
            info="Resolve a deferred AI Overview with a follow-up call. Turn off to keep the deferred stub.",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="The maximum number of search results to return.",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]

    def fetch_content(self) -> list[Data]:
        """Return the organic results as `title` / `url` / `content` / `position` rows."""
        endpoint, body, error = self._safe_call()
        if error is not None or endpoint is None or body is None:
            message = error or "Scavio request failed."
            return [Data(text=message, data={"error": message})]

        # /api/v2/google answers flat: organic_results sits at the top level and each
        # item carries link + snippet (v1's results[] with url + content is retired).
        results = body.get("organic_results", []) or []
        limit = self.max_results or len(results)
        data_results = []
        for result in results[:limit]:
            content = result.get("snippet", "")
            data_results.append(
                Data(
                    text=content,
                    data={
                        "title": result.get("title"),
                        "url": result.get("link"),
                        "content": content,
                        "position": result.get("position"),
                    },
                )
            )
        self.status = data_results
        return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        """Return the organic results as a table."""
        return DataFrame(self.fetch_content())
