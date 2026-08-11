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
    "Location Lookup": Endpoint(
        path="/api/v1/tripadvisor/locations",
        credits=2,
        fields=("query", "limit"),
        required=("query",),
        result_keys=("results",),
    ),
    "Search": Endpoint(
        path="/api/v1/tripadvisor/search",
        credits=2,
        fields=("geo_id", "category", "page", "url"),
    ),
    "Location": Endpoint(
        path="/api/v1/tripadvisor/location",
        credits=2,
        fields=("location_id", "geo_id", "category", "url"),
    ),
    "Reviews": Endpoint(
        path="/api/v1/tripadvisor/reviews",
        credits=2,
        fields=("location_id", "geo_id", "category", "url", "page"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioTripAdvisorComponent(ScavioBaseComponent):
    display_name = "Scavio TripAdvisor"
    description = (
        "TripAdvisor through Scavio: location lookup, search, location, reviews (`/api/v1/tripadvisor/*`, 2 credits "
        "each). Tripadvisor: START HERE. Resolve a place or business NAME to the TripAdvisor geo_id / location_id "
        "pair every other endpoint needs."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioTripAdvisor"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Location Lookup"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Location Lookup"),
        text_input(
            "query",
            "Query",
            "Place or business NAME to resolve into TripAdvisor ids.",
            tool_mode=True,
        ),
        number_input(
            "limit",
            "Limit",
            "Maximum rows to return, 1-20. Default: 12.",
        ),
        text_input(
            "geo_id",
            "Geo ID",
            "TripAdvisor geo id. Accepts 30196, g30196, or a URL carrying one.",
        ),
        choice_input(
            "category",
            "Category",
            (
                "Which family the location belongs to. On reviews it also sets the page size (15 for restaurants, "
                "10 for hotels and attractions), so it must match the location's own type on any page past the "
                "first. Options: restaurants, hotels, attractions. Default: restaurants."
            ),
            ["", "restaurants", "hotels", "attractions"],
            advanced=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 30 locations per page; a page beyond the last is a 404, not an empty result.",
        ),
        text_input(
            "url",
            "URL",
            "Full tripadvisor.com listing URL, usable instead of the ids. Country sites are accepted.",
        ),
        text_input(
            "location_id",
            "Location ID",
            "TripAdvisor location id. Accepts 1899234, d1899234, or a full _Review URL.",
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
