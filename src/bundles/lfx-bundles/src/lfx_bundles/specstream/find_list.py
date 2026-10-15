"""Ask SpecStream for a list on the live web and get every matching row with its source page."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.specstream.base import (
    DEFAULT_WAIT_SECONDS,
    DOCUMENTATION_URL,
    FINISHED,
    STOPPED,
    SpecStreamClient,
)


class SpecStreamFindListComponent(Component):
    """Describe a list in plain words and get back the finished list, one row per match."""

    display_name = "Find List"
    description = (
        "Describe a list in plain words (companies, local businesses, people, grants, tenders, products, "
        "papers, repositories) and get every matching row, each with the page it was read from. "
        "Priced per match, within the maximum you set."
    )
    documentation = DOCUMENTATION_URL
    icon = "SpecStream"
    name = "SpecStreamFindList"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SpecStream API Key",
            info="Create a key under Agents & API in your SpecStream workspace.",
            required=True,
            password=True,
        ),
        MessageTextInput(
            name="request",
            display_name="Request",
            info=(
                "The list to find, in plain words: what every row must be or meet, and the details to bring back. "
                "For example: Roofing companies in Columbus, Ohio with their website and phone."
            ),
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Number of Results",
            info="How many matching rows to find.",
            value=25,
            range_spec=RangeSpec(min=1, max=1000, step_type="int"),
        ),
        FloatInput(
            name="max_price_usd",
            display_name="Maximum Price (USD)",
            info=(
                "The most this list may cost. SpecStream quotes the price ceiling before anything runs; "
                "if it is above this, nothing runs and the component stops with an error."
            ),
            value=5.0,
            required=True,
        ),
        MessageTextInput(
            name="run_key",
            display_name="Run Key",
            info=(
                "Optional. Use the same key to get the run you already started instead of paying for a new one, "
                "for example when a flow retries. Leave empty to use a key built from the request, "
                "the limits and the hour."
            ),
            advanced=True,
        ),
        IntInput(
            name="wait_seconds",
            display_name="Wait (seconds)",
            info="How long to wait for the list to finish before returning the rows found so far.",
            value=DEFAULT_WAIT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="find_list_dataframe"),
        Output(display_name="Rows", name="rows", method="find_list_data"),
    ]

    def set_attributes(self, params: dict) -> None:
        # The graph reuses this instance for later builds and applies the new inputs through
        # set_attributes before each one, so drop the previous build's result here.
        self._specstream_result = None
        super().set_attributes(params)

    def _find(self) -> dict:
        # Both outputs read the same run; fetch it once per component execution.
        cached = getattr(self, "_specstream_result", None)
        if cached is not None:
            return cached
        client = SpecStreamClient(self.api_key)
        result = client.find_list(
            self.request,
            max_results=int(self.max_results),
            max_price_usd=float(self.max_price_usd),
            run_key=str(self.run_key or ""),
            wait_seconds=float(self.wait_seconds if self.wait_seconds not in (None, "") else DEFAULT_WAIT_SECONDS),
        )
        if result["status"] not in FINISHED | STOPPED:
            logger.warning(
                "SpecStream list %s is still running; returning the %d rows found so far.",
                result["list_id"],
                len(result["rows"]),
            )
        self._specstream_result = result
        return result

    def find_list_dataframe(self) -> DataFrame:
        """Return the rows as a table; every row has its ``source_url``."""
        result = self._find()
        self.status = f"{len(result['rows'])} rows ({result['status']}). List: {result['list_link']}"
        return DataFrame(result["rows"])

    def find_list_data(self) -> list[Data]:
        """Return one ``Data`` per row; every row has its ``source_url``."""
        result = self._find()
        self.status = f"{len(result['rows'])} rows ({result['status']}). List: {result['list_link']}"
        return [Data(data=row) for row in result["rows"]]
