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
        path="/api/v1/target/search",
        credits=1,
        fields=("keyword", "page", "count", "sort", "store_id"),
        required=("keyword",),
    ),
    "Category": Endpoint(
        path="/api/v1/target/category",
        credits=1,
        fields=("category_id", "page", "count", "sort", "store_id"),
        required=("category_id",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/target/product",
        credits=1,
        fields=("tcin", "store_id"),
        required=("tcin",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/target/reviews",
        credits=1,
        fields=("tcin", "limit", "store_id"),
        required=("tcin",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioTargetComponent(ScavioBaseComponent):
    display_name = "Scavio Target"
    description = (
        "Target through Scavio: search, category, product details, reviews (`/api/v1/target/*`, 1 credit each). "
        "Search Target.com: prices, ratings, badges and promotions. Pagination: page + count."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioTarget"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "keyword",
            "Keyword",
            "Product search query.",
            tool_mode=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page number, 1-based.",
        ),
        number_input(
            "count",
            "Count",
            "Products per page. Target rejects anything above 28 outright. Default: 24.",
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Sort order for the results. Options: relevance, featured, price_low, price_high, rating_high, "
                "best_seller, newest. Default: relevance."
            ),
            ["", "relevance", "featured", "price_low", "price_high", "rating_high", "best_seller", "newest"],
            advanced=True,
        ),
        text_input(
            "store_id",
            "Store ID",
            (
                "Numeric Target store id. Unlike Walmart this is a real request parameter: it decides prices and "
                "availability. Default: 3991."
            ),
        ),
        text_input(
            "category_id",
            "Category ID",
            "The segment after `N-` in a target.com /c/ URL.",
        ),
        text_input(
            "tcin",
            "TCIN",
            (
                "Target catalog item number. A child TCIN is answered by its variation parent, with the child "
                "present under variants."
            ),
        ),
        number_input(
            "limit",
            "Limit",
            (
                "TRIMS the returned bodies only. Target publishes 8 reviews anonymously and offers no paging, so "
                "this cannot fetch more."
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
