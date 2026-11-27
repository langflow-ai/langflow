from __future__ import annotations

import json

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from lfx_bundles.cleanedweb.cleanedweb_common import error_message, error_rows, make_client

DEFAULT_MAX_ITEMS = 5
MAX_ITEMS = 1000


def _parse_input(raw: object) -> dict | None:
    """The endpoint input as a dict; accepts a dict or a JSON object string."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    msg = 'Run Input must be a JSON object, for example {"search": "python"}.'
    raise ValueError(msg)


class CleanedWebRunAPIComponent(Component):
    """Run one CleanedWeb catalog API endpoint and return its records."""

    display_name = "CleanedWeb Run API"
    description = (
        "Run a maintained CleanedWeb API for a public website and get structured records. "
        "Use CleanedWeb Find API first to get the API id and its inputs. Charged per record delivered."
    )
    documentation = "https://cleanedweb.com/docs/"
    icon = "Globe"

    inputs = [
        MessageTextInput(
            name="api",
            display_name="API",
            required=True,
            info="The API's id or catalog slug, from CleanedWeb Find API.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="endpoint_id",
            display_name="Endpoint",
            info="The endpoint id. Leave empty to use the API's first endpoint.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="run_input",
            display_name="Run Input",
            info='The endpoint\'s input as a JSON object, for example {"search": "python"}.',
            tool_mode=True,
        ),
        IntInput(
            name="max_items",
            display_name="Max Records",
            value=DEFAULT_MAX_ITEMS,
            range_spec=RangeSpec(min=1, max=MAX_ITEMS, step=1, step_type="int"),
            info="Maximum number of records to return (1-1000). Runs are charged per record; start small.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="CleanedWeb API Key",
            required=True,
            info="A key with the run scope. Create one at https://app.cleanedweb.com (5,000 free records).",
            password=True,
        ),
    ]

    outputs = [
        # The method name is the tool name in tool mode; keep it provider specific.
        Output(display_name="Table", name="dataframe", method="cleanedweb_run_api"),
    ]

    def _max_items(self) -> int:
        requested = DEFAULT_MAX_ITEMS if self.max_items is None else int(self.max_items)
        return max(1, min(requested, MAX_ITEMS))

    def fetch_content(self) -> list[Data]:
        if not self.api_key:
            return error_rows("CleanedWeb API key is required. Set the CleanedWeb API Key input.")
        api = (self.api or "").strip()
        if not api:
            return error_rows("Set the API input to an API id or slug from CleanedWeb Find API.")
        try:
            run_input = _parse_input(self.run_input)
            with make_client(self.api_key) as client:
                contract = client.catalog.get(api)
                endpoint_id = (self.endpoint_id or "").strip()
                if not endpoint_id:
                    if not contract.endpoints:
                        return error_rows(f"CleanedWeb API {api} has no endpoints.")
                    endpoint_id = contract.endpoints[0].endpoint_id
                result = client.catalog.run(contract.api_id, endpoint_id, run_input, max_items=self._max_items())
        except Exception as e:  # noqa: BLE001 - surfaced as an error row, never raised into the flow
            return error_rows(error_message(e))
        if not result.complete:
            return error_rows(
                f"The CleanedWeb run has not finished yet (idempotency key {result.idempotency_key}). "
                "Run again with the same inputs later."
            )
        rows = [
            Data(text=json.dumps(record, ensure_ascii=False, default=str), data=record)
            for record in result.records
            if isinstance(record, dict)
        ]
        if not result.is_usable:
            reason = result.stop_reason or result.summary.get("status") or "unknown"
            self.log(f"CleanedWeb run returned {len(rows)} records but is not fully usable: {reason}")
        self.status = rows
        return rows

    def cleanedweb_run_api(self) -> DataFrame:
        """Run the endpoint and return its records as a DataFrame."""
        return DataFrame(self.fetch_content())
