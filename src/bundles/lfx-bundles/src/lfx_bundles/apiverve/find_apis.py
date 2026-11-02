"""Search the APIVerve catalog for an API id and its parameters."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.apiverve.base import DOCUMENTATION_URL, search

MAX_RESULTS = 25


class ApiverveFindApisComponent(Component):
    """Search the public APIVerve catalog. Needs no API key and uses no credits."""

    display_name = "APIVerve Find APIs"
    description = (
        "Search the APIVerve catalog and return matching API ids with their parameters, "
        "ready for APIVerve Run API. Free: it does not call an API."
    )
    documentation = DOCUMENTATION_URL
    icon = "APIVerve"
    name = "ApiverveFindApis"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search",
            info='What you need, for example "vat rates" or "decode vin".',
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"How many matches to return (1-{MAX_RESULTS}).",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="APIs", name="apis", method="find_apis_dataframe")]

    def find_apis(self) -> list[Data]:
        """Return the ranked catalog matches as ``Data`` rows."""
        limit = max(1, min(int(self.max_results or 10), MAX_RESULTS))
        rows = [Data(data=match) for match in search(str(self.query or ""), limit)]
        self.status = rows
        return rows

    def find_apis_dataframe(self) -> DataFrame:
        """Return the ranked catalog matches as a table."""
        return DataFrame(self.find_apis())
