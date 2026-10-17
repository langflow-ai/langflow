from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_twittrapi.components.twittrapi._common import (
    LOCATION_ID_PATTERN,
    api_key_input,
    error_data,
    fetch_page,
    require_digits,
    trend_to_data,
)

WORLDWIDE = "1"


class TwittrAPITrendsComponent(Component):
    """Fetch the trending topics on X (Twitter) for a location."""

    display_name = "TwittrAPI Trends"
    description = "Get trending topics on X (Twitter) for a location, by Yahoo WOEID (1 is worldwide)."
    documentation = "https://www.twittrapi.com/docs/reference/trends-locationid"
    icon = "TwittrAPI"

    inputs = [
        MessageTextInput(
            name="location_id",
            display_name="Location ID (WOEID)",
            value=WORLDWIDE,
            required=True,
            tool_mode=True,
            info="Yahoo WOEID, digits only. 1 is worldwide, 23424977 the United States, 44418 London.",
        ),
        api_key_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="twittrapi_trends"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            location_id = require_digits(self.location_id or WORLDWIDE, LOCATION_ID_PATTERN, "Location ID")
        except ValueError as e:
            rows = [error_data(str(e))]
            self.status = rows
            return rows
        return fetch_page(self, f"/trends/{location_id}", {}, trend_to_data)

    def twittrapi_trends(self) -> DataFrame:
        """Return one row per trend."""
        return DataFrame(self.fetch_content())
