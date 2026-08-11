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
        path="/api/v1/booking/search",
        credits=1,
        fields=(
            "destination",
            "dest_id",
            "dest_type",
            "page",
            "sort_by",
            "min_price",
            "max_price",
            "stars",
            "min_review_score",
            "property_type",
            "free_cancellation",
            "no_prepayment",
            "breakfast_included",
            "checkin",
            "checkout",
            "adults",
            "children_ages",
            "rooms",
            "currency",
        ),
        result_keys=("properties",),
        csv_int_fields=("stars", "children_ages"),
    ),
    "Hotel Details": Endpoint(
        path="/api/v1/booking/hotel",
        credits=1,
        fields=("hotel", "country_code", "checkin", "checkout", "adults", "children_ages", "rooms", "currency"),
        required=("hotel",),
        csv_int_fields=("children_ages",),
    ),
    "Reviews": Endpoint(
        path="/api/v1/booking/reviews",
        credits=1,
        fields=("hotel", "country_code", "checkin", "checkout", "adults", "children_ages", "rooms", "currency"),
        required=("hotel",),
        csv_int_fields=("children_ages",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioBookingComponent(ScavioBaseComponent):
    display_name = "Scavio Booking.com"
    description = (
        "Booking.com through Scavio: search, hotel details, reviews (`/api/v1/booking/*`, 1 credit each). Booking.com "
        "properties for a destination and stay: live nightly price, review score, star rating, room type, deal "
        "badges. Pagination: page -- 25 properties per page."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioBooking"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "destination",
            "Destination",
            (
                "Destination name. Either destination or dest_id is required -- a search with neither returns "
                "Booking's homepage and still costs a credit."
            ),
            tool_mode=True,
        ),
        text_input(
            "dest_id",
            "Dest ID",
            "Booking's numeric destination id.",
        ),
        choice_input(
            "dest_type",
            "Dest Type",
            (
                "What dest_id refers to. Requires dest_id. Options: city, region, country, district, landmark, "
                "airport, hotel."
            ),
            ["", "city", "region", "country", "district", "landmark", "airport", "hotel"],
            advanced=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 25 properties per page.",
        ),
        choice_input(
            "sort_by",
            "Sort By",
            (
                "Sort order for the results. Options: popularity, price_low, price_high, stars_high, stars_low, "
                "stars_and_price, distance, review_score. Default: popularity."
            ),
            [
                "",
                "popularity",
                "price_low",
                "price_high",
                "stars_high",
                "stars_low",
                "stars_and_price",
                "distance",
                "review_score",
            ],
            advanced=True,
        ),
        decimal_input(
            "min_price",
            "Min Price",
            "Minimum price PER NIGHT, in `currency`.",
        ),
        decimal_input(
            "max_price",
            "Max Price",
            "Maximum price PER NIGHT, in `currency`.",
        ),
        text_input(
            "stars",
            "Stars",
            "Star ratings to include. Values are OR'd together.",
        ),
        choice_input(
            "min_review_score",
            "Min Review Score",
            (
                "Minimum guest review score. Only 6, 7, 8 and 9 are accepted -- any other threshold is silently "
                "dropped upstream. Options: 6, 7, 8, 9."
            ),
            ["", "6", "7", "8", "9"],
            advanced=True,
        ),
        text_input(
            "property_type",
            "Property Type",
            (
                "Accommodation type: one of the named values, or a raw numeric Booking accommodation-type id. "
                "Options: apartments, hostels, hotels, motels, resorts, bed_and_breakfasts, villas, campgrounds, "
                "vacation_homes, lodges, homestays."
            ),
        ),
        flag_input(
            "free_cancellation",
            "Free Cancellation",
            "Only return rates with free cancellation.",
        ),
        flag_input(
            "no_prepayment",
            "No Prepayment",
            "Only return rates with no prepayment.",
        ),
        flag_input(
            "breakfast_included",
            "Breakfast Included",
            "Only return rates that include breakfast.",
        ),
        text_input(
            "checkin",
            "Checkin",
            "Check-in date, YYYY-MM-DD. Must be sent together with checkout.",
        ),
        text_input(
            "checkout",
            "Checkout",
            "Check-out date, YYYY-MM-DD. Must be sent together with checkin.",
        ),
        number_input(
            "adults",
            "Adults",
            "Number of adult guests. Default: 2.",
        ),
        text_input(
            "children_ages",
            "Children Ages",
            "Ages of the children in the party, one entry per child. Ages, not a count.",
        ),
        number_input(
            "rooms",
            "Rooms",
            "Number of rooms required. Default: 1.",
        ),
        text_input(
            "currency",
            "Currency",
            "ISO 4217 currency code the prices come back in. Default: USD.",
        ),
        text_input(
            "hotel",
            "Hotel",
            "booking.com property URL or the bare page slug. Query parameters are discarded.",
        ),
        text_input(
            "country_code",
            "Country Code",
            (
                "Two-letter country code. Only consulted when `hotel` is a bare slug; a wrong one is a real, BILLED "
                "404. Default: us."
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
