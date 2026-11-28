"""Search rental cars with Ktemia."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
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
    car_rows,
    search_first_page,
    split_list,
    summarize,
    text_value,
)


class KtemiaCarSearchComponent(Component):
    """Search rental cars and return one row per car with its cheapest seller."""

    display_name = "Ktemia Car Search"
    description = (
        "Search rental cars across rental companies and booking sites. Each row is one car with its agency and "
        "cheapest seller. Needs a pick-up location id from Ktemia Lookup. Pass result_id and token to Ktemia "
        "Booking Options for every seller's price and booking link."
    )
    documentation = f"{DOCUMENTATION_URL}/cars/search/"
    icon = "Ktemia"
    name = "KtemiaCarSearch"

    inputs = [
        SecretStrInput(name="api_key", display_name="Ktemia API Key", info=API_KEY_INFO, required=True),
        MessageTextInput(
            name="pickup_location",
            display_name="Pick-up Location ID",
            info="A car rental location id from Ktemia Lookup (Car rental location).",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="dropoff_location",
            display_name="Drop-off Location ID",
            info="For a one-way rental. Leave empty to return the car where you picked it up.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="pickup_date",
            display_name="Pick-up Date",
            info="YYYY-MM-DD, today or later.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="dropoff_date",
            display_name="Drop-off Date",
            info="YYYY-MM-DD, after pick-up.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="driver_age",
            display_name="Driver Age",
            info="Under 25 often carries a young-driver surcharge. Leave empty for the API default.",
            advanced=True,
        ),
        MessageTextInput(
            name="agencies",
            display_name="Rental Companies",
            info="Only these rental companies, comma-separated ids such as hertz. "
            "The ids are in availableFilters.agency of an earlier search.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(name="country", display_name="Market", info=COUNTRY_INFO, advanced=True),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=DEFAULT_TIMEOUT_SECONDS, advanced=True),
    ]

    outputs = [Output(display_name="Table", name="dataframe", method="search_dataframe")]

    def search(self) -> list[Data]:
        pickup, start, end = (
            text_value(self.pickup_location),
            text_value(self.pickup_date),
            text_value(self.dropoff_date),
        )
        if not (pickup and start and end):
            error = "Enter a pick-up location id (from Ktemia Lookup), a pick-up date, and a drop-off date."
            self.status = error
            return [Data(text=error, data={"error": error})]
        payload = {
            "pickupLocation": pickup,
            "dropoffLocation": text_value(self.dropoff_location) or None,
            "pickupDate": start,
            "dropoffDate": end,
            "driverAge": self.driver_age or None,
            "agencies": split_list(self.agencies) or None,
            "country": text_value(self.country).upper() or None,
        }
        try:
            page = search_first_page(
                "cars", payload, api_key=self.api_key, timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
            )
        except KtemiaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        data = [Data(text=summarize(row), data=row) for row in car_rows(page)]
        if not data:
            note = "No cars matched this search."
            data = [Data(text=note, data={"note": note})]
        self.status = f"{len(data)} cars. {EXPIRY_NOTE}"
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())
