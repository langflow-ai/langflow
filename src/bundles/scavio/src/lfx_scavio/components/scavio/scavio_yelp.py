from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    default_visibility,
    endpoint_input,
    flag_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/yelp/search",
        credits=2,
        fields=("term", "location", "page", "sort", "price", "open_now", "attributes", "url"),
        result_keys=("businesses",),
        csv_fields=("attributes",),
        csv_int_fields=("price",),
    ),
    "Business Details": Endpoint(
        path="/api/v1/yelp/business",
        credits=2,
        fields=("business_id", "url"),
    ),
    "Reviews": Endpoint(
        path="/api/v1/yelp/reviews",
        credits=2,
        fields=("business_id", "url", "page", "sort", "rating"),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioYelpComponent(ScavioBaseComponent):
    display_name = "Scavio Yelp"
    description = (
        "Yelp through Scavio: search, business details, reviews (`/api/v1/yelp/*`, 2 credits each). Businesses in "
        "Yelp's ranked order: rating, review count, price band, categories, address, contact rails, hours, photos, "
        "review snippet. Pagination: page -- Yelp fixes the page size at 10."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioYelp"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "term",
            "Term",
            "What to look for, e.g. 'coffee' or a business name.",
            tool_mode=True,
        ),
        text_input(
            "location",
            "Location",
            (
                "City, neighbourhood or address. Effectively required: without it Yelp geolocates off the proxy "
                "exit and the same request answers about a different metro run to run."
            ),
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. Yelp fixes the page size at 10.",
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Sort order. Closed set: Yelp IGNORES an unrecognised value and serves default ranking under a "
                "billed 200. Options: recommended, rating, review_count. Default: recommended."
            ),
            ["", "recommended", "rating", "review_count"],
            advanced=True,
        ),
        text_input(
            "price",
            "Price",
            "Price bands to include, 1 (cheapest) to 4 (priciest). Options: 1, 2, 3, 4.",
        ),
        flag_input(
            "open_now",
            "Open Now",
            "Only return businesses open right now.",
        ),
        text_input(
            "attributes",
            "Attributes",
            (
                "Raw Yelp filter aliases sent through as attrs, e.g. RestaurantsDelivery, GoodForKids, "
                "WheelchairAccessible. This is a passthrough, not a closed enum: an alias Yelp does not know is "
                "ignored and results come back unfiltered."
            ),
        ),
        text_input(
            "url",
            "URL",
            "Full yelp.com/search URL, usable instead of term plus location.",
        ),
        text_input(
            "business_id",
            "Business ID",
            "Yelp alias (desnudo-coffee-austin-2), opaque encid, or a yelp.com/biz URL.",
        ),
        number_input(
            "rating",
            "Rating",
            (
                "Only return reviews with this star rating. Changes filtered_review_count, not review_count. "
                "Options: 1, 2, 3, 4, 5."
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
