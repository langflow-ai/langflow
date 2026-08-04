from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Hotels Search": Endpoint(
        path="/api/v2/google/hotels",
        credits=1,
        fields=(
            "query",
            "check_in_date",
            "check_out_date",
            "hl",
            "gl",
            "currency",
            "sort_by",
            "min_price",
            "max_price",
            "rating",
            "hotel_class",
            "amenities",
            "property_types",
            "free_cancellation",
            "eco_certified",
            "special_offers",
            "next_page_token",
            "limit",
        ),
        required=("query", "check_in_date", "check_out_date"),
        result_keys=("properties",),
    ),
    "Hotel Detail": Endpoint(
        path="/api/v2/google/hotels/detail",
        credits=1,
        fields=("detail_token", "check_in_date", "check_out_date", "currency", "gl", "hl"),
        required=("detail_token", "check_in_date", "check_out_date"),
        result_keys=("property.booking_sources",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGoogleHotelsComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Google Hotels"
    description = (
        "Google Hotels through Scavio: property search and the booking sources behind a single property "
        "(`/api/v2/google/hotels`, `/api/v2/google/hotels/detail`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleHotels"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Hotels Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Hotels Search"),
        text_input(
            "query",
            "Query",
            "Where to stay. Use the '<City> hotels' form. Max 200 characters.",
            tool_mode=True,
        ),
        text_input("check_in_date", "Check In", "Check-in date as YYYY-MM-DD.", tool_mode=True),
        text_input("check_out_date", "Check Out", "Check-out date as YYYY-MM-DD.", tool_mode=True),
        text_input(
            "detail_token",
            "Detail Token",
            "detail_token taken from a property in a Hotels Search response. Both dates must be resent with it.",
        ),
        number_input("sort_by", "Sort By", "3 lowest price, 8 highest rating, 13 most reviewed."),
        number_input("min_price", "Min Price", "Lower nightly price bound. 0 means no bound."),
        number_input("max_price", "Max Price", "Upper nightly price bound. 0 means no bound."),
        number_input("rating", "Minimum Rating", "7 for 3.5+, 8 for 4.0+, 9 for 4.5+."),
        number_input("limit", "Limit", "Properties per page, 1 to 20."),
        text_input("hotel_class", "Hotel Class", "Comma-separated star classes from 2 to 5, e.g. 4,5.", advanced=True),
        text_input("amenities", "Amenities", "Comma-separated amenity ids.", advanced=True),
        text_input(
            "property_types",
            "Property Types",
            "Comma-separated property type ids. 12 is vacation rentals.",
            advanced=True,
        ),
        text_input(
            "next_page_token", "Next Page Token", "Cursor from a previous Hotels Search response.", advanced=True
        ),
        text_input("currency", "Currency", "Three-letter currency code, e.g. USD.", advanced=True),
        text_input("gl", "Country (gl)", "Two-letter geo country code, e.g. us.", advanced=True),
        text_input("hl", "Language (hl)", "Two-letter interface language code, e.g. en.", advanced=True),
        BoolInput(
            name="free_cancellation",
            display_name="Free Cancellation",
            info="Only properties offering free cancellation.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="eco_certified",
            display_name="Eco Certified",
            info="Only eco-certified properties.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="special_offers",
            display_name="Special Offers",
            info="Only properties currently running a special offer.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
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
