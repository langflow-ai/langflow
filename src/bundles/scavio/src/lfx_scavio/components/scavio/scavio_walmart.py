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
        path="/api/v1/walmart/search",
        credits=1,
        fields=(
            "query",
            "start_page",
            "fulfillment_speed",
            "fulfillment_type",
            "domain",
            "page",
            "sort_by",
            "min_price",
            "max_price",
        ),
        required=("query",),
        result_keys=("products",),
        credit_note="Costs 1 credit on domain com or ca and 2 credits on com.mx.",
    ),
    "Product Details": Endpoint(
        path="/api/v1/walmart/product",
        credits=1,
        fields=("product_id",),
        required=("product_id",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/walmart/reviews",
        credits=1,
        fields=("product_id", "page", "sort"),
        required=("product_id",),
    ),
    "Category": Endpoint(
        path="/api/v1/walmart/category",
        credits=1,
        fields=("category_id", "limit", "fulfillment_speed", "domain", "page", "sort_by", "min_price", "max_price"),
        required=("category_id",),
        result_keys=("products",),
        credit_note="Costs 1 credit on domain com or ca and 2 credits on com.mx.",
    ),
    "Offers": Endpoint(
        path="/api/v1/walmart/offers",
        credits=1,
        fields=("product_id",),
        required=("product_id",),
    ),
    "Seller": Endpoint(
        path="/api/v1/walmart/seller",
        credits=1,
        fields=("seller_id",),
        required=("seller_id",),
    ),
    "Seller Products": Endpoint(
        path="/api/v1/walmart/seller-products",
        credits=1,
        fields=("seller_id",),
        required=("seller_id",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioWalmartComponent(ScavioBaseComponent):
    display_name = "Scavio Walmart"
    description = (
        "Walmart through Scavio: search, product details, reviews, category, offers, seller, seller products "
        "(`/api/v1/walmart/*`; costs 1 credit on domain com or ca and 2 credits on com.mx). Search Walmart and get "
        "structured product rows (products[] + products_count + location). Pagination: page (integer >= 1); "
        "start_page is a deprecated alias."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioWalmart"

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
            "start_page",
            "Start Page",
            "Deprecated alias for page.",
        ),
        choice_input(
            "fulfillment_speed",
            "Fulfillment Speed",
            (
                "Delivery-speed filter. 2_days and anytime are deliberately not offered: 2_days leaks 3-4 day items "
                "and anytime is a no-op, so omit the parameter instead. Options: today, tomorrow."
            ),
            ["", "today", "tomorrow"],
            advanced=True,
        ),
        choice_input(
            "fulfillment_type",
            "Fulfillment Type",
            "Set to in_store to only return pickup stock. Options: in_store.",
            ["", "in_store"],
            advanced=True,
        ),
        choice_input(
            "domain",
            "Domain",
            "Walmart storefront. com and ca cost 1 credit, com.mx costs 2. Options: com, ca, com.mx. Default: com.",
            ["", "com", "ca", "com.mx"],
            advanced=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page number, 1-based.",
        ),
        choice_input(
            "sort_by",
            "Sort By",
            (
                "Sort order for the results. Options: best_match, price_low, price_high, best_seller, rating_high, "
                "new. Default: best_match."
            ),
            ["", "best_match", "price_low", "price_high", "best_seller", "rating_high", "new"],
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
            "product_id",
            "Product ID",
            "Walmart item id (usItemId), e.g. 13544111159.",
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Review sort order. Options: relevancy, submission-desc, submission-asc, rating-desc, rating-asc, "
                "helpful-desc."
            ),
            ["", "relevancy", "submission-desc", "submission-asc", "rating-desc", "rating-asc", "helpful-desc"],
            advanced=True,
        ),
        text_input(
            "category_id",
            "Category ID",
            "Leaf category id (1095191) or the full underscore path (3944_133251_1095191).",
        ),
        number_input(
            "limit",
            "Limit",
            "Trims the products list after fetching. It does NOT reduce the credit cost.",
        ),
        text_input(
            "seller_id",
            "Seller ID",
            "NUMERIC catalog seller id (the seller_catalog_id field). The GUID form of seller_id returns 404.",
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
