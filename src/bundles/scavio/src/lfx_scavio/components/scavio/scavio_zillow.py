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
        path="/api/v1/zillow/search",
        credits=1,
        fields=(
            "location",
            "listing_status",
            "page",
            "sort",
            "min_price",
            "max_price",
            "beds_min",
            "beds_max",
            "baths_min",
            "baths_max",
            "sqft_min",
            "sqft_max",
            "lot_size_min",
            "lot_size_max",
            "year_built_min",
            "year_built_max",
            "max_hoa",
            "home_type",
            "days_on_zillow",
            "keywords",
            "has_pool",
            "has_garage",
            "has_air_conditioning",
            "is_waterfront",
            "has_basement",
            "is_new_construction",
            "has_open_house",
            "price_reduced",
            "is_3d_tour",
        ),
        required=("location",),
        result_keys=("properties",),
    ),
    "Property Details": Endpoint(
        path="/api/v1/zillow/property",
        credits=1,
        fields=("zpid",),
        required=("zpid",),
    ),
    "Agent Reviews": Endpoint(
        path="/api/v1/zillow/reviews",
        credits=1,
        fields=("screen_name",),
        required=("screen_name",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioZillowComponent(ScavioBaseComponent):
    display_name = "Scavio Zillow"
    description = (
        "Zillow through Scavio: search, property details, agent reviews (`/api/v1/zillow/*`, 1 credit each). Zillow "
        "listings in a region: price, beds, baths, living area, Zestimate, coordinates, images, days on market. "
        "Pagination: page."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioZillow"

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
                "Zillow region slug, human city name, ZIP, or a pasted search URL. A bare ZIP works alone but "
                "CANNOT be combined with a filter or a sort -- use the city name there."
            ),
            tool_mode=True,
        ),
        choice_input(
            "listing_status",
            "Listing Status",
            "Which listing state to return. Options: for_sale, for_rent, sold. Default: for_sale.",
            ["", "for_sale", "for_rent", "sold"],
            advanced=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page number, 1-based.",
        ),
        choice_input(
            "sort",
            "Sort",
            (
                "Sort order for the results. Options: relevance, recommended, newest, price_low, price_high, "
                "payment_low, payment_high, beds, baths, sqft, lot_size, zestimate_low, zestimate_high, "
                "recent_change."
            ),
            [
                "",
                "relevance",
                "recommended",
                "newest",
                "price_low",
                "price_high",
                "payment_low",
                "payment_high",
                "beds",
                "baths",
                "sqft",
                "lot_size",
                "zestimate_low",
                "zestimate_high",
                "recent_change",
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
        decimal_input(
            "baths_min",
            "Baths Min",
            "Minimum number of bathrooms. Half-baths allowed (1.5).",
        ),
        decimal_input(
            "baths_max",
            "Baths Max",
            "Maximum number of bathrooms.",
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
            "lot_size_max",
            "Lot Size Max",
            "Maximum lot size in square feet.",
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
            "home_type",
            "Home Type",
            (
                "Property type filter. Options: houses, townhomes, multi_family, condos, apartments, manufactured, "
                "lots_land."
            ),
            ["", "houses", "townhomes", "multi_family", "condos", "apartments", "manufactured", "lots_land"],
            advanced=True,
        ),
        choice_input(
            "days_on_zillow",
            "Days On Zillow",
            (
                "How recently the listing appeared. Closed set: an unrecognised value returns the UNFILTERED result "
                "set under a 200. Options: 1, 7, 14, 30, 90, 6m, 12m, 24m, 36m."
            ),
            ["", "1", "7", "14", "30", "90", "6m", "12m", "24m", "36m"],
            advanced=True,
        ),
        text_input(
            "keywords",
            "Keywords",
            "Extra keywords to match inside the listing text.",
        ),
        flag_input(
            "has_pool",
            "Has Pool",
            "Only return properties with a pool.",
        ),
        flag_input(
            "has_garage",
            "Has Garage",
            "Only return properties with a garage.",
        ),
        flag_input(
            "has_air_conditioning",
            "Has Air Conditioning",
            "Only return properties with air conditioning.",
        ),
        flag_input(
            "is_waterfront",
            "Is Waterfront",
            "Only return waterfront properties.",
        ),
        flag_input(
            "has_basement",
            "Has Basement",
            "Only return properties with a basement.",
        ),
        flag_input(
            "is_new_construction",
            "Is New Construction",
            "Only return new construction.",
        ),
        flag_input(
            "has_open_house",
            "Has Open House",
            "Only return listings with an open house scheduled.",
        ),
        flag_input(
            "price_reduced",
            "Price Reduced",
            "Only return listings whose price was reduced.",
        ),
        flag_input(
            "is_3d_tour",
            "Is 3d Tour",
            "Only return listings with a 3D tour.",
        ),
        text_input(
            "zpid",
            "ZPID",
            (
                "Zillow property id, a /homedetails/ URL, or a zillow.com/apartments/ building URL. Rental "
                "buildings have no visible zpid -- pass the URL."
            ),
        ),
        text_input(
            "screen_name",
            "Screen Name",
            (
                "The AGENT's zillow.com/profile/<name>/ screen name, or the full profile URL. This endpoint "
                "addresses an agent, not a property."
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
