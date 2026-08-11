from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
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
    "Search": Endpoint(
        path="/api/v1/appstore/search",
        credits=1,
        fields=("term", "limit", "country", "entity", "lang"),
        required=("term",),
        result_keys=("apps",),
    ),
    "App Details": Endpoint(
        path="/api/v1/appstore/app",
        credits=1,
        fields=("app_id", "country"),
        required=("app_id",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/appstore/reviews",
        credits=1,
        fields=("app_id", "country", "page", "sort"),
        required=("app_id",),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioAppStoreComponent(ScavioBaseComponent):
    display_name = "Scavio App Store"
    description = (
        "App Store through Scavio: search, app details, reviews (`/api/v1/appstore/*`, 1 credit each). Up to 200 "
        "fully-shaped App Store apps (the same 43-field row as /app). Doubles as a bulk metadata fetch and a "
        "publisher lookup."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioAppStore"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "term",
            "Term",
            (
                "Search term. Matches the app name, a keyword, OR a publisher name -- searching a developer returns "
                "their catalogue."
            ),
            tool_mode=True,
        ),
        number_input(
            "limit",
            "Limit",
            (
                "Apps to return, 1-200. This is the ONLY lever on result volume: App Store search has no pagination "
                "and every offset spelling is silently ignored. Default: 25."
            ),
        ),
        text_input(
            "country",
            "Country",
            (
                "Two-letter storefront code. It decides price, currency, localised title and whether the app is "
                "sold there at all. Anything that is not exactly two letters silently falls back to us. Default: "
                "us."
            ),
        ),
        choice_input(
            "entity",
            "Entity",
            "Which App Store catalogue to search. Options: software, ipad_software, mac_software. Default: software.",
            ["", "software", "ipad_software", "mac_software"],
            advanced=True,
        ),
        text_input(
            "lang",
            "Lang",
            (
                "Five-letter locale, e.g. en_us. Independent of country: the storefront sets the price, this sets "
                "the words."
            ),
        ),
        text_input(
            "app_id",
            "App ID",
            (
                "Numeric App Store id OR a bundle id (notion.id, com.burbn.instagram). A pasted apps.apple.com URL "
                "is rejected with a free 400."
            ),
        ),
        number_input(
            "page",
            "Page",
            (
                "Result page, 1-10, at 50 reviews each. Apple hard-stops at page 10; reach further by asking a "
                "different country. Default: 1."
            ),
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Review sort order. Under most_recent almost every review is too new to have been voted on, so the "
                "vote fields come back as zeroes. Options: most_recent, most_helpful. Default: most_recent."
            ),
            ["", "most_recent", "most_helpful"],
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
