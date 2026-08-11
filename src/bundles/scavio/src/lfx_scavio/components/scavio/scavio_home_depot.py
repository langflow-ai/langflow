from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    decimal_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/homedepot/search",
        credits=2,
        fields=("query", "page", "sort_by", "min_price", "max_price"),
        required=("query",),
        result_keys=("products",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/homedepot/product",
        credits=2,
        fields=("item_id",),
        required=("item_id",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/homedepot/reviews",
        credits=2,
        fields=("item_id", "page"),
        required=("item_id",),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioHomeDepotComponent(ScavioBaseComponent):
    display_name = "Scavio Home Depot"
    description = (
        "Home Depot through Scavio: search, product details, reviews (`/api/v1/homedepot/*`, 2 credits each). Search "
        "Home Depot: price and promotions, brand and model, ratings, badges, per-store pickup/delivery. Pagination: "
        "page -- page size is FIXED at 12 and cannot be changed."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioHomeDepot"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Product search query.",
            tool_mode=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 12 products per page, fixed.",
        ),
        choice_input(
            "sort_by",
            "Sort By",
            (
                "Sort order. The set is closed because Home Depot answers an unknown sort with an empty page rather "
                "than falling back. Options: best_match, top_sellers, top_rated, price_low, price_high. Default: "
                "best_match."
            ),
            ["", "best_match", "top_sellers", "top_rated", "price_low", "price_high"],
            advanced=True,
        ),
        decimal_input(
            "min_price",
            "Min Price",
            "Minimum price filter.",
        ),
        decimal_input(
            "max_price",
            "Max Price",
            "Maximum price filter.",
        ),
        text_input(
            "item_id",
            "Item ID",
            "Home Depot item id or a full homedepot.com/p/... URL. Tracking parameters are discarded.",
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
