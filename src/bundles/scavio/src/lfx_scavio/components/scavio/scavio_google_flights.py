from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    IntInput,
    MessageTextInput,
    api_key_input,
    max_results_input,
)

ENDPOINTS = {
    "Google Flights": Endpoint(
        path="/api/v2/google/flights",
        credits=1,
        fields=(
            "departure_id",
            "arrival_id",
            "outbound_date",
            "return_date",
            "type",
            "adults",
            "children",
            "infants_in_seat",
            "infants_on_lap",
            "travel_class",
            "stops",
            "sort_by",
            "include_airlines",
            "exclude_airlines",
            "hl",
            "gl",
            "currency",
        ),
        required=("departure_id", "arrival_id", "outbound_date"),
        result_keys=("best_flights", "other_flights"),
    ),
}


class ScavioGoogleFlightsComponent(ScavioBaseComponent):
    display_name = "Scavio Google Flights"
    description = (
        "Google Flights through Scavio (`POST /api/v2/google/flights`, 1 credit). Returns the best and "
        "other itineraries for a route and date."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleFlights"

    ENDPOINTS = ENDPOINTS
    DEFAULT_ENDPOINT = "Google Flights"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="departure_id",
            display_name="Departure",
            info="Origin IATA code, e.g. JFK. Comma-separated codes are allowed.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="arrival_id",
            display_name="Arrival",
            info="Destination IATA code, e.g. LHR. Comma-separated codes are allowed.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="outbound_date",
            display_name="Outbound Date",
            info="Departure date as YYYY-MM-DD.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="return_date",
            display_name="Return Date",
            info="Return date as YYYY-MM-DD. Required when Trip Type is 1 (round trip).",
            tool_mode=True,
        ),
        IntInput(
            name="type",
            display_name="Trip Type",
            info="1 round trip, 2 one way, 3 multi-city. 0 leaves it to Google.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="adults",
            display_name="Adults",
            info="Number of adults, 1 to 9. 0 leaves it to Google.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="children",
            display_name="Children",
            info="Number of children, 0 to 9.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="infants_in_seat",
            display_name="Infants In Seat",
            info="Number of infants in their own seat, 0 to 4.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="infants_on_lap",
            display_name="Infants On Lap",
            info="Number of lap infants, 0 to 4.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="travel_class",
            display_name="Travel Class",
            info="1 economy, 2 premium economy, 3 business, 4 first. 0 leaves it to Google.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="stops",
            display_name="Stops",
            info="0 any, 1 nonstop, 2 one stop or fewer, 3 two stops or fewer.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="sort_by",
            display_name="Sort By",
            info="1 top flights, 2 price, 3 departure, 4 arrival, 5 duration, 6 emissions.",
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="include_airlines",
            display_name="Include Airlines",
            info="Comma-separated airline or alliance codes to keep.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_airlines",
            display_name="Exclude Airlines",
            info="Comma-separated airline or alliance codes to drop.",
            advanced=True,
        ),
        MessageTextInput(
            name="currency",
            display_name="Currency",
            info="Three-letter currency code, e.g. USD.",
            advanced=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country (gl)",
            info="Two-letter geo country code, e.g. us.",
            advanced=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language (hl)",
            info="Two-letter interface language code, e.g. en.",
            advanced=True,
        ),
        max_results_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
