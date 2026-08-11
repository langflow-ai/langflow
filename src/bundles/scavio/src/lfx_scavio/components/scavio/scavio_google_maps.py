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
    "Maps Search": Endpoint(
        path="/api/v2/google/maps/search",
        credits=1,
        fields=("query", "start_offset", "ll", "hl", "gl", "google_domain"),
        wire={"start_offset": "start"},
        required=("query",),
        result_keys=("local_results",),
    ),
    "Place Details": Endpoint(
        path="/api/v2/google/maps/place",
        credits=1,
        fields=("place_id", "data_cid"),
        result_keys=("place_results",),
    ),
    "Place Reviews": Endpoint(
        path="/api/v2/google/maps/reviews",
        credits=1,
        fields=("data_id", "place_id", "num", "next_page_token", "reviews_sort_by", "hl", "gl", "google_domain"),
        result_keys=("reviews",),
        wire={"reviews_sort_by": "sort_by"},
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGoogleMapsComponent(ScavioBaseComponent):
    display_name = "Scavio Google Maps"
    description = (
        "Google Maps through Scavio: local search, place details and place reviews "
        "(`/api/v2/google/maps/*`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleMaps"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Maps Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Maps Search"),
        text_input("query", "Query", "What to look for, e.g. coffee shops in Austin.", tool_mode=True),
        text_input(
            "place_id",
            "Place ID",
            "A Google place id (ChIJ...). Place Details needs this or a Data CID; Reviews accepts it too.",
            tool_mode=True,
        ),
        text_input("data_cid", "Data CID", "Numeric Google CID, an alternative to Place ID on Place Details."),
        text_input("data_id", "Data ID", "Reviews identifier in 0xHEX:0xHEX form. Use it or Place ID."),
        text_input(
            "ll",
            "Map Center (ll)",
            "Map center as @lat,lng,zoomz. Maps localizes by map center, not by gl - Scavio derives a "
            "city-level center from gl when this is empty.",
            advanced=True,
        ),
        number_input(
            "start_offset",
            "Start Offset",
            "Result offset. Must be a multiple of 20, max 100. 0 is page 1.",
        ),
        number_input("num", "Number of Reviews", "Reviews per call, 1 to 20."),
        text_input("next_page_token", "Next Page Token", "Reviews cursor from a previous response.", advanced=True),
        choice_input(
            "reviews_sort_by",
            "Reviews Sort",
            "Review ordering. Sent to the API as sort_by.",
            ["", "relevance", "newest", "highest_rating", "lowest_rating"],
            advanced=True,
        ),
        text_input("gl", "Country (gl)", "Two-letter geo country code, e.g. us.", advanced=True),
        text_input("hl", "Language (hl)", "Two-letter interface language code, e.g. en.", advanced=True),
        text_input("google_domain", "Google Domain", "Google domain to query, e.g. google.co.uk.", advanced=True),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
