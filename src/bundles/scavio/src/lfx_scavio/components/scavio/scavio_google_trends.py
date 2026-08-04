from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    choice_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Trends": Endpoint(
        path="/api/v2/google/trends",
        credits=1,
        fields=("query", "geo", "hl", "date", "tz", "data_type", "cat", "gprop", "region"),
        required=("query",),
        result_keys=("interest_by_region", "interest_over_time.timeline_data"),
    ),
    "Trending Now": Endpoint(
        path="/api/v2/google/trending",
        credits=1,
        fields=("geo", "hl", "hours", "trending_cat", "sort", "trend_status"),
        required=("geo",),
        result_keys=("trends",),
        wire={"trending_cat": "cat", "trend_status": "status"},
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGoogleTrendsComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Google Trends"
    description = (
        "Google Trends through Scavio: interest over time and by region for a term, plus the Trending Now "
        "board for a country (`/api/v2/google/trends`, `/api/v2/google/trending`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleTrends"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Trends"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Trends"),
        text_input("query", "Query", "The term to chart interest for.", tool_mode=True),
        text_input(
            "geo",
            "Geo",
            "Uppercase region code, e.g. US, GB or US-CA. Trends is worldwide when empty; Trending Now "
            "requires it. This endpoint family uses geo, not gl.",
            tool_mode=True,
        ),
        text_input("hl", "Language (hl)", "Two-letter interface language code, e.g. en.", advanced=True),
        text_input(
            "date",
            "Date Range",
            "Free-text time range, e.g. today 12-m or 2024-01-01 2024-12-31.",
            advanced=True,
        ),
        text_input("tz", "Timezone Offset", "Timezone offset in minutes, sent as a string.", advanced=True),
        choice_input(
            "data_type",
            "Data Type",
            "Which Trends dataset to return. Empty returns the upstream default (timeseries plus geo map).",
            ["", "TIMESERIES", "GEO_MAP", "GEO_MAP_0", "RELATED_QUERIES", "RELATED_TOPICS"],
            advanced=True,
        ),
        text_input("cat", "Category", "Trends category id as a string, e.g. 71.", advanced=True),
        choice_input(
            "gprop",
            "Property",
            "Google property to chart. Empty means web search.",
            ["", "images", "news", "youtube", "froogle"],
            advanced=True,
        ),
        choice_input(
            "region",
            "Region Breakdown",
            "Granularity of the interest-by-region breakdown.",
            ["", "COUNTRY", "REGION", "DMA", "CITY"],
            advanced=True,
        ),
        number_input("hours", "Hours", "Trending Now window in hours: 4, 24, 48 or 168."),
        number_input("trending_cat", "Trending Category", "Trending Now category id, 0 to 20. 0 is all."),
        choice_input(
            "sort",
            "Sort",
            "Trending Now ordering. The field is sort here, not sort_by.",
            ["", "relevance", "search_volume", "recency", "title"],
            advanced=True,
        ),
        choice_input(
            "trend_status",
            "Status",
            "Trending Now status filter. Sent to the API as status.",
            ["", "all", "active"],
            advanced=True,
        ),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
