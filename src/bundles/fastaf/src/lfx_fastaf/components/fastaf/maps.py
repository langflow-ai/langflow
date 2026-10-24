from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError, integer_option
from lfx_fastaf._inputs import (
    api_key_input,
    localization_inputs,
    optional_int,
    query_input,
    text_input,
)


class FastAFMapsComponent(FastAFBaseComponent):
    display_name = "FastAF Search Maps"
    description = "Find Google Maps places or retrieve place details for 5 credits per execution."
    name = "FastAFMaps"
    endpoint = "maps"
    result_keys = ("search_results",)
    inputs = [
        api_key_input(),
        query_input(required=False),
        text_input(
            "place_id",
            "Place ID",
            "Google place_id from a previous Maps result; use instead of a query.",
            tool_mode=True,
        ),
        text_input("location", "Search Centre", "Place name, e.g. Rome, Italy. Cannot combine with coordinates."),
        text_input("coordinates", "Coordinates", "Centre as @latitude,longitude,zoom, e.g. @41.9028,12.4964,13z."),
        optional_int("page", "Result Offset", "0, 20, 40, 60, 80 or 100. Supply coordinates for pagination."),
        *localization_inputs(),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_maps")]

    def request_body(self) -> dict:
        if not (self.query or "").strip() and not (self.place_id or "").strip():
            msg = "Supply a query or place ID."
            raise FastAFError(msg)
        if self.location and self.coordinates:
            msg = "Choose a search centre or coordinates, not both."
            raise FastAFError(msg)
        return {
            "query": self.query,
            "place_id": self.place_id,
            "location": self.location,
            "ll": self.coordinates,
            "page": integer_option(self.page, "Result Offset", 0, 100, 20),
            **self.localization(),
        }

    def fastaf_maps(self) -> DataFrame:
        return DataFrame(self.fetch_content())
