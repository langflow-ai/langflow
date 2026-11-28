"""Resolve a place or airline name to the codes Ktemia searches need."""

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
    KtemiaAPIError,
    ktemia_request,
    summarize,
    text_value,
)

# kind -> (path, list key in the response)
LOOKUPS = {
    "Airport": ("/flights/airports", "airports"),
    "Airline": ("/flights/airlines", "airlines"),
    "Hotel location": ("/hotels/locations", "locations"),
    "Car rental location": ("/cars/locations", "locations"),
}


class KtemiaLookupComponent(Component):
    """Look up airports, airlines, hotel locations, or car rental locations by name."""

    display_name = "Ktemia Lookup"
    description = (
        "Turn a place or airline name into the code a Ktemia search needs: an IATA code for flights, "
        "or a location id for hotels and cars. Several places can share a name, so check the matches."
    )
    documentation = f"{DOCUMENTATION_URL}/hotels/locations/"
    icon = "Ktemia"
    name = "KtemiaLookup"

    inputs = [
        SecretStrInput(name="api_key", display_name="Ktemia API Key", info=API_KEY_INFO, required=True),
        DropdownInput(
            name="kind",
            display_name="Look Up",
            options=list(LOOKUPS),
            value="Hotel location",
            info="What to look up. Hotel and car searches need a location id from this lookup.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Name",
            info="A city, airport, neighborhood, or airline name, such as London, JFK, or Lufthansa.",
            required=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Table", name="dataframe", method="lookup_dataframe")]

    def lookup(self) -> list[Data]:
        query = text_value(self.query)
        if not query:
            error = "Enter a name to look up."
            self.status = error
            return [Data(text=error, data={"error": error})]
        path, key = LOOKUPS.get(self.kind, LOOKUPS["Hotel location"])
        try:
            body = ktemia_request(
                "GET",
                path,
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"query": query},
            )
        except KtemiaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        matches = [item for item in body.get(key) or [] if isinstance(item, dict)]
        data = [Data(text=summarize(item), data=item) for item in matches]
        self.status = data
        return data

    def lookup_dataframe(self) -> DataFrame:
        return DataFrame(self.lookup())
