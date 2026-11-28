"""Every seller's price and booking link for one Ktemia result."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.ktemia.ktemia_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    VERTICALS,
    KtemiaAPIError,
    booking_option_rows,
    ktemia_request,
    summarize,
    text_value,
)


class KtemiaBookingOptionsComponent(Component):
    """Expand one flight, hotel, or car into every seller with a price and booking link."""

    display_name = "Ktemia Booking Options"
    description = (
        "Get every seller's price and booking link for one result from a Ktemia flight, hotel, or car search. "
        "Use the result_id and token from that search's row. Ktemia compares; the traveller books on the "
        "seller's site, so return booking_url exactly as given."
    )
    documentation = f"{DOCUMENTATION_URL}/flights/details/"
    icon = "Ktemia"
    name = "KtemiaBookingOptions"

    inputs = [
        SecretStrInput(name="api_key", display_name="Ktemia API Key", info=API_KEY_INFO, required=True),
        DropdownInput(
            name="vertical",
            display_name="Search Type",
            options=list(VERTICALS),
            value="flights",
            info="The search the result came from.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="token",
            display_name="Token",
            info="The token column of the search row.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="result_id",
            display_name="Result ID",
            info="The result_id column of the search row.",
            required=True,
            tool_mode=True,
        ),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=DEFAULT_TIMEOUT_SECONDS, advanced=True),
    ]

    outputs = [Output(display_name="Table", name="dataframe", method="options_dataframe")]

    def booking_options(self) -> list[Data]:
        vertical = self.vertical if self.vertical in VERTICALS else "flights"
        token, result_id = text_value(self.token), text_value(self.result_id)
        if not (token and result_id):
            error = "Enter the token and result_id from a Ktemia search row."
            self.status = error
            return [Data(text=error, data={"error": error})]
        try:
            details = ktemia_request(
                "GET",
                f"/{vertical}/details",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"token": token, "resultId": result_id},
            )
        except KtemiaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        data = [Data(text=summarize(row), data=row) for row in booking_option_rows(vertical, details)]
        if not data:
            note = "No sellers returned for this result. The token may have expired: run the search again."
            data = [Data(text=note, data={"note": note})]
        self.status = data
        return data

    def options_dataframe(self) -> DataFrame:
        return DataFrame(self.booking_options())
