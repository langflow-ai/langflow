from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    cursor_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/googleplay/search",
        credits=2,
        fields=("query", "hl", "gl"),
        required=("query",),
        result_keys=("results",),
    ),
    "App Details": Endpoint(
        path="/api/v1/googleplay/app",
        credits=2,
        fields=("app_id", "hl", "gl"),
        required=("app_id",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/googleplay/reviews",
        credits=2,
        fields=("app_id", "sort", "count", "cursor", "hl", "gl"),
        required=("app_id",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGooglePlayComponent(ScavioBaseComponent):
    display_name = "Scavio Google Play"
    description = (
        "Google Play through Scavio: search, app details, reviews (`/api/v1/googleplay/*`, 2 credits each). Ranked "
        "Google Play apps: package name, title, developer, rating, install count, price and IAP range, content "
        "rating, icon, screenshots."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGooglePlay"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Search query. There is no pagination -- one shelf of ~30 apps.",
            tool_mode=True,
        ),
        text_input(
            "hl",
            "Language",
            (
                "Interface language. It moves the whole storefront, not only the strings: title, description, "
                "install formatting and content rating all follow it. Default: en."
            ),
        ),
        text_input(
            "gl",
            "Country",
            "Storefront country code. Default: us.",
        ),
        text_input(
            "app_id",
            "App ID",
            "Android package name, or any play.google.com URL carrying one in its id parameter.",
        ),
        choice_input(
            "sort",
            "Sort",
            "Review sort order. Options: relevance, newest, rating. Default: newest.",
            ["", "relevance", "newest", "rating"],
            advanced=True,
        ),
        number_input(
            "count",
            "Count",
            "Reviews to return, 1-200. Default: 50.",
        ),
        cursor_input(
            (
                "next_cursor from a previous response. OPAQUE and SINGLE-USE, and it encodes the sort as well as "
                "the position -- send it back with the SAME sort it came from. A cursor past the last review is a "
                "404."
            ),
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
