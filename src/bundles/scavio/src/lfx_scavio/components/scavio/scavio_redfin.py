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
        path="/api/v1/redfin/search",
        credits=1,
        fields=(
            "location",
            "region_id",
            "region_type",
            "listing_status",
            "sold_within_days",
            "page",
            "limit",
            "sort",
            "min_price",
            "max_price",
            "beds_min",
            "beds_max",
            "baths_min",
            "sqft_min",
            "sqft_max",
            "lot_size_min",
            "year_built_min",
            "year_built_max",
            "max_hoa",
            "property_type",
            "has_pool",
            "max_days_on_market",
            "min_days_on_market",
        ),
    ),
    "Property Details": Endpoint(
        path="/api/v1/redfin/property",
        credits=1,
        fields=("property_id",),
        required=("property_id",),
    ),
    "Market": Endpoint(
        path="/api/v1/redfin/market",
        credits=1,
        fields=("location", "region_id", "region_type"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioRedfinComponent(ScavioBaseComponent):
    display_name = "Scavio Redfin"
    description = (
        "Redfin through Scavio: search, property details, market (`/api/v1/redfin/*`, 1 credit each). Redfin "
        "listings: price, price per sqft, beds, baths, living area, lot size, year built, coordinates, listing "
        "remarks, full photo galleries. Pagination: page + limit -- up to 350 per page."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioRedfin"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "location",
            "Location",
            (
                "A redfin.com region URL (/city/, /neighborhood/, /county/, /zipcode/) or a bare 5-digit ZIP. CITY "
                "NAMES ARE NOT ACCEPTED."
            ),
            tool_mode=True,
        ),
        number_input(
            "region_id",
            "Region ID",
            (
                "Redfin's own numeric region id. NOT a ZIP code -- different number spaces, and a ZIP here resolves "
                "to another city rather than failing. Must be sent together with region_type."
            ),
        ),
        number_input(
            "region_type",
            "Region Type",
            (
                "What region_id refers to: 1 neighborhood, 2 ZIP, 5 county, 6 city. Must be sent together with "
                "region_id. Options: 1, 2, 5, 6."
            ),
        ),
        choice_input(
            "listing_status",
            "Listing Status",
            "Which listing state to return. Options: for_sale, sold, for_rent. Default: for_sale.",
            ["", "for_sale", "sold", "for_rent"],
            advanced=True,
        ),
        number_input(
            "sold_within_days",
            "Sold Within Days",
            (
                "How far back to look for sold homes. Only valid with listing_status=sold, where it defaults to 90. "
                "Default: 90."
            ),
        ),
        number_input(
            "page",
            "Page",
            "Result page number, 1-based.",
        ),
        number_input(
            "limit",
            "Limit",
            "Listings per page, 1-350. Default: 100.",
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Sort order for the results. Options: recommended, price_low, price_high, newest, oldest, sqft_low, "
                "sqft_high, price_per_sqft_low, price_per_sqft_high. Default: recommended."
            ),
            [
                "",
                "recommended",
                "price_low",
                "price_high",
                "newest",
                "oldest",
                "sqft_low",
                "sqft_high",
                "price_per_sqft_low",
                "price_per_sqft_high",
            ],
            advanced=True,
        ),
        decimal_input(
            "min_price",
            "Min Price",
            "Minimum price. On listing_status=for_rent this means MONTHLY RENT.",
        ),
        decimal_input(
            "max_price",
            "Max Price",
            "Maximum price. On listing_status=for_rent this means MONTHLY RENT.",
        ),
        number_input(
            "beds_min",
            "Beds Min",
            "Minimum number of bedrooms.",
        ),
        number_input(
            "beds_max",
            "Beds Max",
            "Maximum number of bedrooms.",
        ),
        number_input(
            "baths_min",
            "Baths Min",
            (
                "Minimum number of bathrooms. WHOLE baths only -- fractional bounds are rejected because Redfin "
                "truncates them."
            ),
        ),
        number_input(
            "sqft_min",
            "Sq Ft Min",
            "Minimum living area in square feet.",
        ),
        number_input(
            "sqft_max",
            "Sq Ft Max",
            "Maximum living area in square feet.",
        ),
        number_input(
            "lot_size_min",
            "Lot Size Min",
            "Minimum lot size in square feet.",
        ),
        number_input(
            "year_built_min",
            "Year Built Min",
            "Earliest year built.",
        ),
        number_input(
            "year_built_max",
            "Year Built Max",
            "Latest year built.",
        ),
        decimal_input(
            "max_hoa",
            "Max HOA",
            "Maximum monthly HOA fee.",
        ),
        choice_input(
            "property_type",
            "Property Type",
            "Property type filter. Options: house, condo, townhouse, multi_family, land, other, co_op.",
            ["", "house", "condo", "townhouse", "multi_family", "land", "other", "co_op"],
            advanced=True,
        ),
        flag_input(
            "has_pool",
            "Has Pool",
            "Only return properties with a pool.",
        ),
        number_input(
            "max_days_on_market",
            "Max Days On Market",
            (
                "Maximum days on market. Cannot be combined with min_days_on_market: Redfin expresses both through "
                "one parameter."
            ),
        ),
        number_input(
            "min_days_on_market",
            "Min Days On Market",
            "Minimum days on market. Cannot be combined with max_days_on_market.",
        ),
        text_input(
            "property_id",
            "Property ID",
            "Redfin property id or any redfin.com listing URL carrying one.",
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
