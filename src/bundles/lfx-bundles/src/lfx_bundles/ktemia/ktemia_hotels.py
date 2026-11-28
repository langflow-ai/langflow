"""Search hotels with Ktemia."""

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
    hotel_rows,
    search_first_page,
    split_list,
    summarize,
    text_value,
)

SORTS = ["bestValue", "price", "rating", "stars", "distance"]


class KtemiaHotelSearchComponent(Component):
    """Search hotels and return one row per hotel with its cheapest seller."""

    display_name = "Ktemia Hotel Search"
    description = (
        "Search hotels across booking sites such as Booking.com, Expedia, Hotels.com, and Agoda. Each row is one "
        "hotel with its cheapest seller. Needs a location id from Ktemia Lookup. Pass result_id and token to "
        "Ktemia Booking Options for every seller's price and booking link."
    )
    documentation = f"{DOCUMENTATION_URL}/hotels/search/"
    icon = "Ktemia"
    name = "KtemiaHotelSearch"

    inputs = [
        SecretStrInput(name="api_key", display_name="Ktemia API Key", info=API_KEY_INFO, required=True),
        MessageTextInput(
            name="location",
            display_name="Location ID",
            info="A hotel location id from Ktemia Lookup (Hotel location), such as 29230 for London.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="checkin", display_name="Check-in", info="YYYY-MM-DD, today or later.", required=True, tool_mode=True
        ),
        MessageTextInput(
            name="checkout", display_name="Check-out", info="YYYY-MM-DD, after check-in.", required=True, tool_mode=True
        ),
        IntInput(name="adults", display_name="Adults", value=2, tool_mode=True),
        IntInput(name="rooms", display_name="Rooms", value=1, advanced=True),
        IntInput(name="min_stars", display_name="Min Stars", info="1 to 5. Leave empty for any.", advanced=True),
        IntInput(name="max_price", display_name="Max Price", info="Per stay, in the market's currency.", advanced=True),
        MessageTextInput(
            name="providers",
            display_name="Booking Sites",
            info="Only these booking sites, comma-separated, such as Booking.com, Expedia. "
            "The ids are in availableFilters.bookingSites of an earlier search.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(name="country", display_name="Market", info=COUNTRY_INFO, advanced=True),
        DropdownInput(name="sort_by", display_name="Sort By", options=SORTS, value="bestValue", advanced=True),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=DEFAULT_TIMEOUT_SECONDS, advanced=True),
    ]

    outputs = [Output(display_name="Table", name="dataframe", method="search_dataframe")]

    def search(self) -> list[Data]:
        location, checkin, checkout = text_value(self.location), text_value(self.checkin), text_value(self.checkout)
        if not (location and checkin and checkout):
            error = "Enter a location id (from Ktemia Lookup), a check-in date, and a check-out date (YYYY-MM-DD)."
            self.status = error
            return [Data(text=error, data={"error": error})]
        payload = {
            "location": location,
            "checkin": checkin,
            "checkout": checkout,
            "adults": int(self.adults) if self.adults else None,
            "rooms": int(self.rooms) if self.rooms else None,
            "minStars": self.min_stars or None,
            "maxPrice": self.max_price or None,
            "providers": split_list(self.providers) or None,
            "country": text_value(self.country).upper() or None,
            "sortBy": self.sort_by,
        }
        try:
            page = search_first_page(
                "hotels", payload, api_key=self.api_key, timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
            )
        except KtemiaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        data = [Data(text=summarize(row), data=row) for row in hotel_rows(page)]
        self.status = f"{len(data)} hotels. {EXPIRY_NOTE}"
        if not data:
            note = "No hotels matched this search."
            data = [Data(text=note, data={"note": note})]
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
