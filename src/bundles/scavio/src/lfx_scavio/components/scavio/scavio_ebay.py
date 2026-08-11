from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    decimal_input,
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
        path="/api/v1/ebay/search",
        credits=1,
        fields=(
            "query",
            "seller",
            "page",
            "sort_by",
            "min_price",
            "max_price",
            "condition",
            "buying_format",
            "free_shipping",
            "sold",
            "category_id",
            "per_page",
        ),
        result_keys=("products",),
    ),
    "Listing Details": Endpoint(
        path="/api/v1/ebay/product",
        credits=1,
        fields=("item_id",),
        required=("item_id",),
    ),
    "Seller Profile": Endpoint(
        path="/api/v1/ebay/seller",
        credits=1,
        fields=("seller",),
        required=("seller",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioEbayComponent(ScavioBaseComponent):
    display_name = "Scavio eBay"
    description = (
        "eBay through Scavio: search, listing details, seller profile (`/api/v1/ebay/*`, 1 credit each). Search live "
        "or SOLD eBay listings: price, condition, bids, shipping, seller, feedback. Pagination: page; per_page "
        "accepts ONLY 60, 120 or 240 (silent fallback to 60)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioEbay"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Keyword query. Optional: a seller-scoped search works with no query at all.",
            tool_mode=True,
        ),
        text_input(
            "seller",
            "Seller",
            (
                "Scope the search to one seller. Works with no query, which is the only paginated way to list a "
                "seller's whole catalogue."
            ),
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
                "Sort order for the results. Options: best_match, ending_soonest, newly_listed, price_low, "
                "price_high. Default: best_match."
            ),
            ["", "best_match", "ending_soonest", "newly_listed", "price_low", "price_high"],
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
        choice_input(
            "condition",
            "Condition",
            (
                "Item condition. refurbished is eBay's parent condition, not one of its three graded tiers. "
                "Options: new, open_box, refurbished, used, for_parts."
            ),
            ["", "new", "open_box", "refurbished", "used", "for_parts"],
            advanced=True,
        ),
        choice_input(
            "buying_format",
            "Buying Format",
            "Listing format filter. Options: auction, buy_it_now, best_offer.",
            ["", "auction", "buy_it_now", "best_offer"],
            advanced=True,
        ),
        flag_input(
            "free_shipping",
            "Free Shipping",
            "Only return listings with free shipping.",
        ),
        flag_input(
            "sold",
            "Sold",
            (
                "Search completed listings that actually SOLD -- the price-research view. eBay publishes no "
                "headline count there, so total_results comes back null."
            ),
        ),
        text_input(
            "category_id",
            "Category ID",
            "Numeric eBay category id. A non-numeric value returns the UNFILTERED set under a 200.",
        ),
        number_input(
            "per_page",
            "Per Page",
            (
                "Listings per page. eBay accepts only 60, 120 or 240 and silently falls back to 60 for anything "
                "else. Options: 60, 120, 240. Default: 60."
            ),
        ),
        text_input(
            "item_id",
            "Item ID",
            "eBay item number or a full ebay.com/itm/... URL. Tracking parameters are discarded.",
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
