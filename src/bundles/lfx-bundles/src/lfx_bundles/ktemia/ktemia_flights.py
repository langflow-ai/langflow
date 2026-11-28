"""Search flights with Ktemia."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.ktemia.ktemia_common import (
    API_KEY_INFO,
    COUNTRY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    EXPIRY_NOTE,
    KtemiaAPIError,
    flight_rows,
    search_first_page,
    split_list,
    summarize,
    text_value,
)

CABINS = ["economy", "premiumEconomy", "business", "first"]
SORTS = ["bestValue", "price", "duration", "departure", "arrival"]


class KtemiaFlightSearchComponent(Component):
    """Search one-way or round-trip flights and return one row per itinerary."""

    display_name = "Ktemia Flight Search"
    description = (
        "Search flights across airlines and booking sites. Each row is one itinerary with its cheapest price, "
        "seller, and how many sellers offer it. Pass result_id and token to Ktemia Booking Options for every "
        "seller's price and booking link."
    )
    documentation = f"{DOCUMENTATION_URL}/flights/search/"
    icon = "Ktemia"
    name = "KtemiaFlightSearch"

    inputs = [
        SecretStrInput(name="api_key", display_name="Ktemia API Key", info=API_KEY_INFO, required=True),
        MessageTextInput(
            name="origin",
            display_name="Origin",
            info="IATA airport or city code, such as JFK or NYC. Use Ktemia Lookup to find a code.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="destination",
            display_name="Destination",
            info="IATA airport or city code, such as LAX or LON.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="departure_date",
            display_name="Departure Date",
            info="YYYY-MM-DD, today or later. Ask for the date instead of guessing it.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="return_date",
            display_name="Return Date",
            info="YYYY-MM-DD for a round trip. Leave empty for one way.",
            tool_mode=True,
        ),
        IntInput(name="adults", display_name="Adults", value=1, info="Travellers aged 12 and over.", tool_mode=True),
        DropdownInput(name="cabin", display_name="Cabin", options=CABINS, value="economy", advanced=True),
        IntInput(
            name="max_stops",
            display_name="Max Stops",
            info="Maximum stops per leg. 0 is non-stop only. Leave empty for any.",
            advanced=True,
        ),
        MessageTextInput(
            name="airlines",
            display_name="Airlines",
            info="Only these airlines: comma-separated IATA codes, such as UA, DL.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(name="country", display_name="Market", info=COUNTRY_INFO, advanced=True),
        DropdownInput(name="sort_by", display_name="Sort By", options=SORTS, value="bestValue", advanced=True),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=DEFAULT_TIMEOUT_SECONDS, advanced=True),
    ]

    outputs = [Output(display_name="Table", name="dataframe", method="search_dataframe")]

    def search(self) -> list[Data]:
        origin, destination = text_value(self.origin).upper(), text_value(self.destination).upper()
        departure = text_value(self.departure_date)
        if not (origin and destination and departure):
            error = "Enter an origin, a destination, and a departure date (YYYY-MM-DD)."
            self.status = error
            return [Data(text=error, data={"error": error})]
        payload = {
            "origin": origin,
            "destination": destination,
            "departureDate": departure,
            "returnDate": text_value(self.return_date) or None,
            "passengers": {"adults": int(self.adults)} if self.adults else None,
            "cabin": self.cabin,
            "maxStops": self.max_stops if self.max_stops not in (None, "") else None,
            "airlines": [code.upper() for code in split_list(self.airlines)] or None,
            "country": text_value(self.country).upper() or None,
            "sortBy": self.sort_by,
        }
        try:
            page = search_first_page(
                "flights", payload, api_key=self.api_key, timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
            )
        except KtemiaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        data = [Data(text=summarize(row), data=row) for row in flight_rows(page)]
        if not data:
            note = "No flights matched this search."
            data = [Data(text=note, data={"note": note})]
        self.status = f"{len(data)} itineraries. {EXPIRY_NOTE}"
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
