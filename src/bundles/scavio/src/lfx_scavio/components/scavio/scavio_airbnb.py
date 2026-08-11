from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    cursor_input,
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
        path="/api/v1/airbnb/search",
        credits=1,
        fields=(
            "location",
            "check_in",
            "check_out",
            "adults",
            "children",
            "infants",
            "pets",
            "min_price",
            "max_price",
            "room_type",
            "min_bedrooms",
            "min_beds",
            "min_bathrooms",
            "superhost",
            "instant_book",
            "guest_favorite",
            "free_cancellation",
            "amenities",
            "currency",
            "page",
            "cursor",
        ),
        required=("location",),
        result_keys=("listings",),
    ),
    "Listing Details": Endpoint(
        path="/api/v1/airbnb/listing",
        credits=1,
        fields=("listing_id", "check_in", "check_out", "adults", "children", "infants", "pets", "currency"),
        required=("listing_id",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/airbnb/reviews",
        credits=1,
        fields=("listing_id", "currency", "limit", "offset"),
        required=("listing_id",),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioAirbnbComponent(ScavioBaseComponent):
    display_name = "Scavio Airbnb"
    description = (
        "Airbnb through Scavio: search, listing details, reviews (`/api/v1/airbnb/*`, 1 credit each). Airbnb stays: "
        "stay-total and per-night price with the full discount ledger, rating, bedrooms/beds/baths, coordinates, "
        "badges, images. Pagination: page XOR cursor -- `cursor` WINS over `page`, so sending both is REJECTED. 18 "
        "listings per page."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioAirbnb"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "location",
            "Location",
            "City, region, ZIP, or a pasted airbnb.com/s/ URL. An unresolvable place is a 404.",
            tool_mode=True,
        ),
        text_input(
            "check_in",
            "Check In",
            (
                "Check-in date, YYYY-MM-DD. Must be sent with check_out. Omitting both makes Airbnb A/B both the "
                "window AND the prices -- the response flags that as dates_are_defaulted. Default: +30d when "
                "omitted (transport)."
            ),
        ),
        text_input(
            "check_out",
            "Check Out",
            "Check-out date, YYYY-MM-DD. Must be sent with check_in. Default: check_in + 5 nights when omitted.",
        ),
        number_input(
            "adults",
            "Adults",
            "Number of adult guests.",
        ),
        number_input(
            "children",
            "Children",
            "Number of children in the party (ages 2-12).",
        ),
        number_input(
            "infants",
            "Infants",
            "Number of infants in the party.",
        ),
        number_input(
            "pets",
            "Pets",
            "Number of pets travelling.",
        ),
        decimal_input(
            "min_price",
            "Min Price",
            "Minimum WHOLE-STAY total, not a per-night rate.",
        ),
        decimal_input(
            "max_price",
            "Max Price",
            "Maximum WHOLE-STAY total, not a per-night rate.",
        ),
        choice_input(
            "room_type",
            "Room Type",
            "Room type filter. Options: entire_home, private_room, shared_room, hotel_room.",
            ["", "entire_home", "private_room", "shared_room", "hotel_room"],
            advanced=True,
        ),
        number_input(
            "min_bedrooms",
            "Min Bedrooms",
            "Minimum number of bedrooms.",
        ),
        number_input(
            "min_beds",
            "Min Beds",
            "Minimum number of beds.",
        ),
        number_input(
            "min_bathrooms",
            "Min Bathrooms",
            "Minimum number of bathrooms.",
        ),
        flag_input(
            "superhost",
            "Superhost",
            "Only return Superhost listings.",
        ),
        flag_input(
            "instant_book",
            "Instant Book",
            "Only return instant-book listings.",
        ),
        flag_input(
            "guest_favorite",
            "Guest Favorite",
            "Only return Guest Favourite listings.",
        ),
        flag_input(
            "free_cancellation",
            "Free Cancellation",
            "Only return listings with free cancellation.",
        ),
        text_input(
            "amenities",
            "Amenities",
            (
                "Comma-separated amenity filter. Named vocabulary: wifi, air_conditioning, pool, kitchen, "
                "free_parking, washer, self_check_in, tv -- or raw numeric Airbnb amenity ids. An unrecognised NAME "
                "is rejected before the scrape. Options: wifi, air_conditioning, pool, kitchen, free_parking, "
                "washer, self_check_in, tv."
            ),
        ),
        text_input(
            "currency",
            "Currency",
            "ISO 4217 currency code the prices come back in. Default: USD.",
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 18 listings per page. Cannot be combined with cursor.",
        ),
        cursor_input(
            "next_cursor from a previous response. Wins over page, so sending both is rejected.",
        ),
        text_input(
            "listing_id",
            "Listing ID",
            (
                "Airbnb listing id or a full /rooms/ URL. Query parameters are discarded because they carry someone "
                "else's dates."
            ),
        ),
        number_input(
            "limit",
            "Limit",
            (
                "Reviews per page, 1-50. Airbnb returns a fixed 7 when no explicit limit is sent, so always set it. "
                "Default: 30."
            ),
        ),
        number_input(
            "offset",
            "Offset",
            "Zero-based review offset for paging. Default: 0.",
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
